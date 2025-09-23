#!/usr/bin/env python3
"""
ACCSM - ACC Server Manager
Modulo di pulizia e manutenzione del sistema

Questo modulo si occupa di:
- Controllo configurazione e database
- Svuotamento cartella risultati
- Eliminazione piloti senza sessioni
"""

import json
import logging
import sqlite3
import shutil
from pathlib import Path
from typing import Dict, Optional


class ACCSystemCleaner:
    """Classe per operazioni di pulizia del sistema ACCSM"""
    
    def __init__(self, config_file='acc_config.json'):
        """Inizializza il sistema di pulizia ACC"""
        self.config_file = config_file
        self.config = None
        self.db_path = None
        
    def load_config(self) -> bool:
        """Carica e verifica il file di configurazione"""
        if not Path(self.config_file).exists():
            print(f"❌ File di configurazione non trovato: {self.config_file}")
            return False
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Verifica presenza chiavi essenziali
            required_keys = ['database', 'paths']
            for key in required_keys:
                if key not in self.config:
                    print(f"❌ Chiave mancante in configurazione: {key}")
                    return False
            
            self.db_path = self.config['database']['path']
            print(f"✅ Configurazione caricata correttamente")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Errore parsing JSON configurazione: {e}")
            return False
        except Exception as e:
            print(f"❌ Errore caricamento configurazione: {e}")
            return False
    
    def check_database(self) -> bool:
        """Verifica esistenza e accessibilità database"""
        if not self.db_path:
            print("❌ Percorso database non configurato")
            return False
        
        if not Path(self.db_path).exists():
            print(f"❌ Database non trovato: {self.db_path}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            if not tables:
                print("❌ Database vuoto o corrotto")
                return False
            
            print(f"✅ Database accessibile ({len(tables)} tabelle)")
            return True
            
        except Exception as e:
            print(f"❌ Errore accesso database: {e}")
            return False
    
    def organize_results_folder(self) -> bool:
        """Organizza la cartella risultati spostando i file in sottocartelle appropriate"""
        if 'local_results' not in self.config['paths']:
            print("❌ Percorso cartella risultati non configurato")
            return False
        
        results_path = Path(self.config['paths']['local_results'])
        
        if not results_path.exists():
            print(f"⚠️  Cartella risultati non esiste: {results_path}")
            print("✅ Creazione cartella risultati")
            results_path.mkdir(parents=True, exist_ok=True)
            return True
        
        try:
            # Trova solo file JSON nella cartella principale (esclude sottocartelle)
            json_files = [f for f in results_path.iterdir() if f.is_file() and f.suffix.lower() == '.json']
            
            if not json_files:
                print("ℹ️  Nessun file JSON da organizzare nella cartella risultati")
                return True
            
            print(f"📁 Trovati {len(json_files)} file JSON da organizzare")
            
            # Identifica file non presenti nel database (sessioni vuote)
            files_not_in_db = self._get_files_not_in_database(json_files)
            files_in_db = [f for f in json_files if f not in files_not_in_db]
            
            print(f"📊 Analisi file:")
            print(f"   🗑️  Sessioni vuote da eliminare: {len(files_not_in_db)}")
            print(f"   📁 Sessioni da organizzare: {len(files_in_db)}")
            
            if files_not_in_db:
                print("\n🗑️  File sessioni vuote che verranno eliminati:")
                for empty_file in files_not_in_db:
                    print(f"   - {empty_file.name}")
            
            # Conferma utente
            confirm = input("\nVuoi procedere con eliminazione e organizzazione? (s/N): ").strip().lower()
            
            if confirm not in ['s', 'si', 'sì', 'y', 'yes']:
                print("❌ Operazione annullata dall'utente")
                return False
            
            # FASE 1: Elimina file di sessioni vuote
            deleted_count = 0
            for empty_file in files_not_in_db:
                try:
                    empty_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️  Errore eliminazione {empty_file.name}: {e}")
            
            if deleted_count > 0:
                print(f"🗑️  Eliminati {deleted_count} file di sessioni vuote")
            
            # FASE 2: Organizza file rimanenti
            if not files_in_db:
                print("ℹ️  Nessun file rimanente da organizzare")
                return True
            
            # Crea cartelle di destinazione
            unofficial_dir = results_path / "unofficial_sessions"
            official_dir = results_path / "official_sessions"
            unofficial_dir.mkdir(exist_ok=True)
            official_dir.mkdir(exist_ok=True)
            
            moved_files = 0
            official_count = 0
            unofficial_count = 0
            
            # Processa ogni file rimanente
            for json_file in files_in_db:
                file_info = self._get_file_session_info(json_file.name)
                
                if file_info['is_official'] and file_info['competition_name']:
                    # File di competizione ufficiale
                    competition_folder = self._create_competition_folder(
                        official_dir, 
                        file_info['competition_name'],
                        file_info['competition_date']
                    )
                    destination = competition_folder / json_file.name
                    official_count += 1
                else:
                    # File di sessione non ufficiale
                    destination = unofficial_dir / json_file.name
                    unofficial_count += 1
                
                # Sposta il file
                shutil.move(str(json_file), str(destination))
                moved_files += 1
            
            # Report finale dettagliato
            print(f"\n✅ Operazione completata:")
            print(f"   🗑️  File eliminati (sessioni vuote): {deleted_count}")
            print(f"   📁 Sessioni ufficiali organizzate: {official_count}")
            print(f"   📁 Sessioni non ufficiali organizzate: {unofficial_count}")
            print(f"   📦 Totale file spostati: {moved_files}")
            print(f"   📊 Totale file processati: {deleted_count + moved_files}")
            return True
            
        except Exception as e:
            print(f"❌ Errore organizzazione cartella risultati: {e}")
            return False
    
    def _get_file_session_info(self, filename: str) -> dict:
        """Ottiene informazioni sulla sessione dal database basandosi sul filename"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query per ottenere informazioni sulla sessione
            cursor.execute('''
                SELECT s.competition_id, c.name as competition_name,
                       c.date_start, c.round_number, s.session_date
                FROM sessions s
                LEFT JOIN competitions c ON s.competition_id = c.competition_id
                WHERE s.filename = ?
            ''', (filename,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                competition_id, comp_name, comp_date, round_num, session_date = result
                return {
                    'is_official': competition_id is not None,
                    'competition_name': comp_name,
                    'competition_date': comp_date or session_date,
                    'round_number': round_num
                }
            else:
                # File non presente nel database = non ufficiale
                return {
                    'is_official': False,
                    'competition_name': None,
                    'competition_date': None,
                    'round_number': None
                }
                
        except Exception as e:
            print(f"⚠️  Errore accesso database per {filename}: {e}")
            # In caso di errore, considera come non ufficiale
            return {
                'is_official': False,
                'competition_name': None,
                'competition_date': None,
                'round_number': None
            }
    
    def _create_competition_folder(self, base_dir: Path, comp_name: str, comp_date: str) -> Path:
        """Crea cartella per competizione con formato [data]_[nome]"""
        try:
            # Formatta la data per il nome cartella
            if comp_date:
                # Estrai solo la data (senza ora) e formatta come YYYY-MM-DD
                date_part = comp_date.split('T')[0] if 'T' in comp_date else comp_date.split(' ')[0]
                date_formatted = date_part.replace('-', '_')
            else:
                date_formatted = "unknown_date"
            
            # Pulisci il nome della competizione per uso come nome cartella
            safe_name = "".join(c for c in comp_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            
            folder_name = f"{date_formatted}_{safe_name}"
            competition_dir = base_dir / folder_name
            competition_dir.mkdir(exist_ok=True)
            
            return competition_dir
            
        except Exception as e:
            print(f"⚠️  Errore creazione cartella competizione: {e}")
            # Fallback a cartella generica
            fallback_dir = base_dir / "unknown_competition"
            fallback_dir.mkdir(exist_ok=True)
            return fallback_dir
    
    def _get_files_not_in_database(self, json_files: list) -> list:
        """Identifica file JSON che non sono presenti nel database (sessioni vuote)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Ottieni tutti i filename presenti nel database
            cursor.execute('SELECT filename FROM sessions')
            db_filenames = set(row[0] for row in cursor.fetchall())
            conn.close()
            
            # Trova file non presenti nel database
            files_not_in_db = []
            for json_file in json_files:
                if json_file.name not in db_filenames:
                    files_not_in_db.append(json_file)
            
            return files_not_in_db
            
        except Exception as e:
            print(f"⚠️  Errore controllo file nel database: {e}")
            return []
    
    def delete_drivers_without_sessions(self) -> bool:
        """Elimina piloti che non hanno mai partecipato a sessioni"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Trova piloti senza sessioni
            cursor.execute('''
                SELECT d.driver_id, d.last_name 
                FROM drivers d 
                LEFT JOIN session_results sr ON d.driver_id = sr.driver_id 
                WHERE sr.driver_id IS NULL
            ''')
            
            orphaned_drivers = cursor.fetchall()
            
            if not orphaned_drivers:
                print("ℹ️  Nessun pilota senza sessioni trovato")
                conn.close()
                return True
            
            print(f"⚠️  Trovati {len(orphaned_drivers)} piloti senza sessioni:")
            for driver_id, last_name in orphaned_drivers:
                print(f"   - {last_name} ({driver_id})")
            
            # Conferma utente
            confirm = input("Vuoi procedere con l'eliminazione? (s/N): ").strip().lower()
            
            if confirm not in ['s', 'si', 'sì', 'y', 'yes']:
                print("❌ Operazione annullata dall'utente")
                conn.close()
                return False
            
            # Elimina piloti orfani
            for driver_id, _ in orphaned_drivers:
                cursor.execute('DELETE FROM drivers WHERE driver_id = ?', (driver_id,))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Eliminati {len(orphaned_drivers)} piloti senza sessioni")
            return True
            
        except Exception as e:
            print(f"❌ Errore eliminazione piloti senza sessioni: {e}")
            return False


class ACCCleanMenu:
    """Menu per operazioni di pulizia"""
    
    def __init__(self):
        self.cleaner = ACCSystemCleaner()
        
    def display_menu(self):
        """Visualizza il menu delle operazioni di pulizia"""
        print("\n" + "="*50)
        print("🧹 ACCSM - Pulizia e Manutenzione")
        print("="*50)
        print("1. Organizza cartella risultati")
        print("2. Elimina piloti senza sessioni")
        print("0. Torna al menu principale")
        print("="*50)
    
    def run(self):
        """Esegue il menu delle operazioni di pulizia"""
        # Controlli iniziali
        print("🔍 Verifica sistema...")
        
        if not self.cleaner.load_config():
            input("\n❌ Errore configurazione. Premi INVIO per uscire...")
            return
        
        if not self.cleaner.check_database():
            input("\n❌ Errore database. Premi INVIO per uscire...")
            return
        
        print("✅ Sistema verificato correttamente")
        
        while True:
            self.display_menu()
            
            choice = input("\n➤ Seleziona operazione: ").strip()
            
            if choice == '0':
                print("\n👋 Ritorno al menu principale...")
                break
            elif choice == '1':
                print("\n📁 Organizzazione cartella risultati...")
                success = self.cleaner.organize_results_folder()
                if success:
                    input("\n✅ Operazione completata. Premi INVIO per continuare...")
                else:
                    input("\n❌ Operazione fallita. Premi INVIO per continuare...")
            elif choice == '2':
                print("\n🧹 Eliminazione piloti senza sessioni...")
                success = self.cleaner.delete_drivers_without_sessions()
                if success:
                    input("\n✅ Operazione completata. Premi INVIO per continuare...")
                else:
                    input("\n❌ Operazione fallita. Premi INVIO per continuare...")
            else:
                print(f"\n❌ Opzione non valida: {choice}")
                input("⚠️  Premi INVIO per continuare...")


def main():
    """Funzione principale"""
    try:
        menu = ACCCleanMenu()
        menu.run()
    except KeyboardInterrupt:
        print("\n\n⏹️  Programma interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ Errore generico: {e}")


if __name__ == "__main__":
    main()