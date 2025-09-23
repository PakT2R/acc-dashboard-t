#!/usr/bin/env python3
"""
competitions_acc.py - Script per gestione competizioni ACC
Estratto da manager_acc.py per renderlo autonomo
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple



class CompetitionsManager:
    """Manager per la gestione delle competizioni ACC"""
    
    def __init__(self, db_path: str = None, config_path: str = None):
        """Inizializza il manager delle competizioni"""
        self.script_dir = Path(__file__).parent
        
        # Carica configurazione
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self.script_dir / "acc_config.json"
            
        # Verifica config e database
        self._check_files()
        
        # Se arriviamo qui, i file esistono
        self.config = self._load_config()
        
        # Percorso database dal config o parametro
        if db_path:
            self.db_path = db_path
        elif self.config and 'database' in self.config:
            self.db_path = self.config['database']['path']
        else:
            self.db_path = self.script_dir / "acc_stats.db"
        
        # Setup logging
        self.logger = self._setup_logging()
    
    def _check_files(self):
        """Verifica che config e database esistano"""
        config_exists = self.config_path.exists()
        db_exists = (self.script_dir / "acc_stats.db").exists()
        
        if not config_exists:
            print(f"⚠️  File config non trovato: {self.config_path}")
        
        if not db_exists:
            print(f"❌ Database non trovato: {self.script_dir / 'acc_stats.db'}")
        
        if not config_exists or not db_exists:
            sys.exit(1)
        
    def _load_config(self) -> dict:
        """Carica configurazione da file JSON"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️  File config non trovato: {self.config_path}")
                return None
        except Exception as e:
            print(f"❌ Errore caricamento config: {e}")
            return None
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging per il script"""
        logger = logging.getLogger('competitions_acc')
        logger.setLevel(logging.INFO)
        
        # Handler per file
        log_file = self.script_dir / "competitions_acc.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        return logger
    
    
    def show_competitions_menu(self):
        """Menu gestione competizioni"""
        while True:
            print(f"\n{'='*50}")
            print(f"🏁 GESTIONE COMPETIZIONI")
            print(f"{'='*50}")
            print("\n📋 OPZIONI:")
            print("  1. Mostra competizioni")
            print("  2. Mostra sessioni non assegnate")
            print("  3. Assegnazione automatica sessioni")
            print("  0. Esci")
            
            choice = input("\nScelta: ").strip()

            if choice == "1":
                self._show_competitions_with_sessions()
            elif choice == "2":
                self._show_unassigned_sessions()
            elif choice == "3":
                self.auto_assign_sessions_to_competitions()
            elif choice == "0":
                print("\n👋 Uscita da gestione competizioni")
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")

    def _show_competitions_with_sessions(self):
        """Mostra competizioni e le loro sessioni"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.round_number,
                       ch.name as championship_name, ch.season,
                       COUNT(s.session_id) as session_count
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                LEFT JOIN sessions s ON c.competition_id = s.competition_id
                GROUP BY c.competition_id
                ORDER BY ch.season DESC, c.round_number
            ''')
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print("\n📭 Nessuna competizione trovata")
                conn.close()
                return
            
            print(f"\n🏁 COMPETIZIONI:")
            for comp_id, comp_name, track, round_num, champ_name, season, session_count in competitions:
                champ_info = f"{champ_name} ({season})" if champ_name else "Competizione libera"
                print(f"\n🏆 {comp_name} - {champ_info}")
                print(f"  📍 {track} | 🎮 {session_count} sessioni")
                
                # Mostra sessioni della competizione
                cursor.execute('''
                    SELECT session_id, session_type, session_date, total_drivers, session_order
                    FROM sessions 
                    WHERE competition_id = ?
                    ORDER BY session_order, session_date
                ''', (comp_id,))
                
                comp_sessions = cursor.fetchall()
                for sess_id, sess_type, sess_date, drivers, order in comp_sessions:
                    try:
                        date_obj = datetime.fromisoformat(sess_date)
                        date_str = date_obj.strftime('%d/%m %H:%M')
                    except:
                        date_str = sess_date[:16]
                    
                    print(f"    • {sess_type:<4} - {date_str} - {drivers} piloti - {sess_id}")

            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione competizioni: {e}")
            print(f"❌ Errore visualizzazione competizioni: {e}")

    def _show_unassigned_sessions(self):
        """Mostra sessioni non assegnate"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, filename, session_type, track_name, 
                       session_date, total_drivers
                FROM sessions 
                WHERE competition_id IS NULL
                ORDER BY session_date DESC
            ''')
            
            sessions = cursor.fetchall()
            
            if not sessions:
                print("\n✅ Nessuna sessione non assegnata")
                conn.close()
                return
            
            print(f"\n⏳ SESSIONI NON ASSEGNATE ({len(sessions)}):")
            print(f"{'ID':<17} {'Tipo':<4} {'Pista':<15} {'Data':<12} {'Piloti':<7} {'File'}")
            print("-" * 70)
            
            for session_id, filename, session_type, track, date, drivers in sessions:
                try:
                    date_obj = datetime.fromisoformat(date)
                    date_str = date_obj.strftime('%d/%m/%Y')
                except:
                    date_str = date[:10]
                
                track_display = track[:13] + ".." if len(track) > 15 else track
                print(f"{session_id:<17} {session_type:<4} {track_display:<15} {date_str:<12} {drivers:<7} {filename}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione sessioni non assegnate: {e}")
            print(f"❌ Errore visualizzazione sessioni non assegnate: {e}")

    def auto_assign_sessions_to_competitions(self):
        """Trova sessioni non assegnate e le raggruppa automaticamente per weekend"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*60}")
            print(f"🔄 ASSEGNAZIONE AUTOMATICA SESSIONI")
            print(f"{'='*60}")
            
            # Trova sessioni non assegnate
            cursor.execute('''
                SELECT session_id, filename, session_type, track_name, 
                       session_date, total_drivers
                FROM sessions 
                WHERE competition_id IS NULL
                ORDER BY session_date, track_name
            ''')
            
            unassigned_sessions = cursor.fetchall()
            
            if not unassigned_sessions:
                print("ℹ️  Nessuna sessione non assegnata trovata")
                conn.close()
                return
            
            print(f"📊 Trovate {len(unassigned_sessions)} sessioni non assegnate")
            
            # Raggruppa sessioni per weekend (stessa pista, date vicine)
            weekend_groups = self._group_sessions_by_weekend(unassigned_sessions)
            
            print(f"\n🗓️  Rilevati {len(weekend_groups)} potenziali weekend:")
            
            assignments_made = 0
            
            for i, group in enumerate(weekend_groups, 1):
                print(f"\n📋 GRUPPO {i}:")
                print(f"  🏁 Pista: {group['track']}")
                print(f"  📅 Date: {group['date_start']} - {group['date_end']}")
                print(f"  🎮 Sessioni: {len(group['sessions'])}")
                
                # Mostra sessioni del gruppo
                for session in group['sessions']:
                    session_id, filename, session_type, track, date, drivers = session
                    date_str = datetime.fromisoformat(date).strftime('%d/%m %H:%M')
                    print(f"    • {session_type:<4} - {date_str} - {drivers} piloti - {filename}")
                
                # Chiedi conferma per creare competizione
                create = input(f"\n🤔 Creare competizione per questo gruppo? (s/N): ").strip().lower()
                
                if create in ['s', 'si', 'sì', 'y', 'yes']:
                    # Cerca campionato attivo o permetti creazione
                    championship_result = self._select_or_create_championship(cursor)
                    
                    if championship_result == "SKIP":
                        print("⏭️  Gruppo saltato")
                        continue
                    
                    # championship_result può essere: int (ID campionato), None (competizione libera), o "SKIP"
                    championship_id = championship_result
                    
                    # Crea competizione
                    competition_id = self._create_competition_for_group(cursor, group, championship_id)
                    
                    if competition_id:
                        # Assegna sessioni alla competizione
                        session_count = self._assign_sessions_to_competition(cursor, group['sessions'], competition_id)
                        assignments_made += session_count
                        
                        if championship_id:
                            print(f"✅ Competizione creata nel campionato e {session_count} sessioni assegnate")
                        else:
                            print(f"✅ Competizione libera creata e {session_count} sessioni assegnate")
                    else:
                        print("❌ Errore creazione competizione")
                else:
                    print("⏭️  Gruppo saltato")
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ ASSEGNAZIONE COMPLETATA")
            print(f"📊 Sessioni assegnate: {assignments_made}")
            
        except Exception as e:
            self.logger.error(f"❌ Errore assegnazione automatica: {e}")
            print(f"❌ Errore assegnazione automatica: {e}")

    def _group_sessions_by_weekend(self, sessions) -> List[Dict]:
        """Raggruppa sessioni per weekend (stessa pista, date vicine)"""
        groups = []
        
        for session in sessions:
            session_id, filename, session_type, track, date, drivers = session
            session_date = datetime.fromisoformat(date)
            
            # Cerca se può essere aggiunta a un gruppo esistente
            added_to_group = False
            
            for group in groups:
                # Stesso track e data entro 3 giorni
                if (group['track'] == track and 
                    abs((session_date - group['date_start']).days) <= 3):
                    
                    group['sessions'].append(session)
                    group['date_end'] = max(group['date_end'], session_date)
                    group['date_start'] = min(group['date_start'], session_date)
                    added_to_group = True
                    break
            
            # Se non aggiunta, crea nuovo gruppo
            if not added_to_group:
                groups.append({
                    'track': track,
                    'date_start': session_date,
                    'date_end': session_date,
                    'sessions': [session]
                })
        
        return groups

    def _select_or_create_championship(self, cursor) -> Optional[int]:
        """Seleziona campionato esistente o ne crea uno nuovo"""
        try:
            # Lista campionati attivi
            cursor.execute('''
                SELECT championship_id, name, season, description
                FROM championships 
                WHERE is_completed = FALSE
                ORDER BY season DESC, name
            ''')
            
            active_championships = cursor.fetchall()
            
            print("\n🏆 OPZIONI DISPONIBILI:")
            print("  0. Crea nuovo campionato")
            print("  -1. Competizione libera (senza campionato)")
            print("  -2. Lascia sessioni libere (senza competizione)")
            
            for i, (champ_id, name, season, desc) in enumerate(active_championships, 1):
                season_str = f" ({season})" if season else ""
                print(f"  {i}. {name}{season_str}")
            
            try:
                choice = input(f"\nScelta (-2 a {len(active_championships)}): ").strip()
                choice_int = int(choice)
                
                if choice_int == -2:
                    return "SKIP"  # Indica di non creare competizione
                elif choice_int == -1:
                    return None  # Competizione libera (championship_id = NULL)
                elif choice_int == 0:
                    return self._create_new_championship(cursor)
                elif 1 <= choice_int <= len(active_championships):
                    return active_championships[choice_int - 1][0]
                else:
                    print("❌ Scelta non valida")
                    return "SKIP"
                    
            except ValueError:
                print("❌ Input non valido")
                return "SKIP"
                
        except Exception as e:
            self.logger.error(f"❌ Errore selezione campionato: {e}")
            print(f"❌ Errore selezione campionato: {e}")
            return "SKIP"

    def _create_new_championship(self, cursor) -> Optional[int]:
        """Crea nuovo campionato"""
        try:
            print("\n📝 CREAZIONE NUOVO CAMPIONATO:")
            
            name = input("Nome campionato: ").strip()
            if not name:
                print("❌ Nome obbligatorio")
                return None
            
            season = input("Stagione (es: 2025) [opzionale]: ").strip()
            season = int(season) if season.isdigit() else None
            
            description = input("Descrizione [opzionale]: ").strip()
            description = description if description else None
            
            # Inserisci campionato
            cursor.execute('''
                INSERT INTO championships (name, season, description, created_at)
                VALUES (?, ?, ?, ?)
            ''', (name, season, description, datetime.now().isoformat()))
            
            championship_id = cursor.lastrowid
            print(f"✅ Campionato '{name}' creato con ID {championship_id}")
            
            return championship_id
            
        except Exception as e:
            self.logger.error(f"❌ Errore creazione campionato: {e}")
            print(f"❌ Errore creazione campionato: {e}")
            return None

    def _create_competition_for_group(self, cursor, group: Dict, championship_id: Optional[int]) -> Optional[int]:
        """Crea competizione per un gruppo di sessioni"""
        try:
            # Nome automatico basato su pista e data
            track = group['track']
            date_start = group['date_start'].strftime('%Y-%m-%d')
            
            # Determina numero round se parte di campionato
            if championship_id:
                cursor.execute('''
                    SELECT COALESCE(MAX(round_number), 0) + 1 
                    FROM competitions 
                    WHERE championship_id = ?
                ''', (championship_id,))
                round_number = cursor.fetchone()[0]
                suggested_name = f"Round {round_number} - {track}"
            else:
                round_number = None
                suggested_name = f"{track} - {date_start}"
            
            # Chiedi nome personalizzato
            print(f"\n📝 NOME COMPETIZIONE:")
            print(f"Nome suggerito: '{suggested_name}'")
            custom_name = input("Nome personalizzato [INVIO per usare quello suggerito]: ").strip()
            
            # Usa nome personalizzato o quello suggerito
            comp_name = custom_name if custom_name else suggested_name
            
            # Determina formato weekend
            session_types = [session[2] for session in group['sessions']]
            if any('R' in st for st in session_types):
                if len([st for st in session_types if 'R' in st]) > 1:
                    weekend_format = "sprint"  # Multiple races
                else:
                    weekend_format = "standard"  # Single race
            else:
                weekend_format = "practice"  # Solo prove
            
            # Inserisci competizione
            cursor.execute('''
                INSERT INTO competitions 
                (championship_id, name, round_number, track_name, date_start, date_end, 
                 weekend_format, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                championship_id, comp_name, round_number, track,
                group['date_start'].strftime('%Y-%m-%d'),
                group['date_end'].strftime('%Y-%m-%d'),
                weekend_format, datetime.now().isoformat()
            ))
            
            competition_id = cursor.lastrowid
            print(f"🏁 Competizione '{comp_name}' creata")
            
            return competition_id
            
        except Exception as e:
            self.logger.error(f"❌ Errore creazione competizione: {e}")
            print(f"❌ Errore creazione competizione: {e}")
            return None

    def _assign_sessions_to_competition(self, cursor, sessions: List, competition_id: int) -> int:
        """Assegna sessioni a una competizione con session_order basato sull'ordinamento temporale"""
        try:
            # Estrai i filename dalle sessioni per calcolare il session_order
            session_filenames = []
            for session in sessions:
                session_id, filename, session_type, track, date, drivers = session
                session_filenames.append(filename)
            
            # Ordina i filename temporalmente (stesso principio del load_json_results)
            sorted_filenames = sorted(session_filenames)
            
            # Crea mapping filename -> session_order
            filename_to_order = {}
            for order, filename in enumerate(sorted_filenames, 1):
                filename_to_order[filename] = order
            
            assigned_count = 0
            
            for session in sessions:
                session_id, filename, session_type, track, date, drivers = session
                
                # Ottieni session_order dal mapping basato sull'ordinamento temporale
                session_order = filename_to_order.get(filename, 1)
                
                # Aggiorna sessione con competition_id e session_order
                cursor.execute('''
                    UPDATE sessions 
                    SET competition_id = ?, session_order = ?
                    WHERE session_id = ?
                ''', (competition_id, session_order, session_id))
                
                assigned_count += 1
                
                # Log per debug
                self.logger.debug(f"📋 Assegnata sessione {session_id} ({session_type}) a competizione {competition_id} con order {session_order}")
            
            # Marca la competizione come completata
            if assigned_count > 0:
                cursor.execute('''
                    UPDATE competitions 
                    SET is_completed = TRUE
                    WHERE competition_id = ?
                ''', (competition_id,))
                
                self.logger.info(f"✅ Competizione {competition_id} marcata come completata con {assigned_count} sessioni")
            
            return assigned_count
            
        except Exception as e:
            self.logger.error(f"❌ Errore assegnazione sessioni: {e}")
            print(f"❌ Errore assegnazione sessioni: {e}")
            return 0








def main():
    """Funzione principale"""
    try:
        print("🏁 ACC Competitions Manager - Avvio...")
        
        # Inizializza manager
        manager = CompetitionsManager()
        
        # Avvia menu principale
        manager.show_competitions_menu()
        
    except KeyboardInterrupt:
        print("\n\n👋 Interruzione utente - Uscita...")
    except Exception as e:
        print(f"\n❌ Errore critico: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()