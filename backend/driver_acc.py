#!/usr/bin/env python3
"""
ACC Bad Driver Manager - Gestione autonoma segnalazioni piloti
Strumento per importazione e analisi segnalazioni bad driver per ACC
"""

import sqlite3
import json
import os
import logging
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class BadDriverManager:
    """Gestione autonoma segnalazioni bad driver per ACC"""
    
    def __init__(self, config_path: str = "acc_config.json"):
        """Inizializza manager con configurazione"""
        self.config = self.load_config(config_path)
        self.db_path = self.config['database']['path']
        self.setup_logging()
        
        # Verifica esistenza database
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database non trovato: {self.db_path}")
    
    def load_config(self, config_path: str) -> dict:
        """Carica configurazione"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"File di configurazione non trovato: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Errore parsing configurazione: {e}")
    
    def setup_logging(self):
        """Configura logging"""
        log_dir = Path(self.config['paths']['logs'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"bad_driver_manager_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def show_menu(self):
        """Mostra menu principale"""
        while True:
            print(f"\n{'='*50}")
            print(f"🚨 GESTIONE BAD DRIVER ACC")
            print(f"{'='*50}")
            print("\n📋 OPZIONI:")
            print("  1. Importa segnalazioni")
            print("  2. Mostra statistiche")
            print("  0. Esci")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                self.import_bad_driver_reports()
            elif choice == "2":
                self.show_bad_driver_statistics()
            elif choice == "0":
                print("\n👋 Arrivederci!")
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")
    
    def import_bad_driver_reports(self):
        """Importa segnalazioni bad driver da file"""
        try:
            print("\n🚨 IMPORT SEGNALAZIONI BAD DRIVER")
            
            bad_players_dir = Path(self.config['paths']['bad_players'])
            bad_players_dir.mkdir(parents=True, exist_ok=True)
            
            # Lista file disponibili
            report_files = []
            for ext in ['.json', '.csv', '.txt', '.log']:
                report_files.extend(list(bad_players_dir.glob(f'*{ext}')))
            
            if not report_files:
                print(f"❌ Nessun file di segnalazioni trovato in: {bad_players_dir}")
                print("📝 Formati supportati: .json, .csv, .txt, .log")
                return
            
            print("\n📁 FILE DISPONIBILI:")
            for i, file in enumerate(report_files, 1):
                print(f"  {i}. {file.name}")
            
            try:
                choice = int(input(f"\nScegli file (1-{len(report_files)}): ").strip()) - 1
                if not 0 <= choice < len(report_files):
                    print("❌ Scelta non valida")
                    return
            except ValueError:
                print("❌ Input non valido")
                return
            
            selected_file = report_files[choice]
            print(f"\n📂 File selezionato: {selected_file.name}")
            
            # Determina tipo file e processa
            if selected_file.suffix.lower() == '.json':
                reports_data = self._parse_json_reports(selected_file)
            elif selected_file.suffix.lower() == '.csv':
                reports_data = self._parse_csv_reports(selected_file)
            else:  # .txt, .log o altri
                reports_data = self._parse_text_reports(selected_file)
            
            if not reports_data:
                print("❌ Nessuna segnalazione valida trovata nel file")
                return
            
            # Processa segnalazioni
            self._process_bad_driver_reports(reports_data, selected_file.name)
            
        except Exception as e:
            self.logger.error(f"❌ Errore import segnalazioni: {e}")
            print(f"❌ Errore durante import: {e}")
    
    def _parse_json_reports(self, filepath: Path) -> List[Dict]:
        """Parse file JSON segnalazioni"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            reports = []
            
            # Formato atteso: array di oggetti o oggetto con array "reports"
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and 'reports' in data:
                items = data['reports']
            else:
                print("❌ Formato JSON non riconosciuto")
                return []
            
            for item in items:
                if all(key in item for key in ['reporter_id', 'reported_id', 'reported_nickname']):
                    reports.append({
                        'reporter_id': str(item['reporter_id']).strip(),
                        'reported_id': str(item['reported_id']).strip(),
                        'reported_nickname': str(item['reported_nickname']).strip()
                    })
            
            print(f"🔍 Trovate {len(reports)} segnalazioni nel file JSON")
            return reports
            
        except Exception as e:
            self.logger.error(f"❌ Errore parsing file JSON: {e}")
            print(f"❌ Errore parsing JSON: {e}")
            return []
    
    def _parse_csv_reports(self, filepath: Path) -> List[Dict]:
        """Parse file CSV segnalazioni"""
        try:
            reports = []
            
            with open(filepath, 'r', encoding='utf-8') as f:
                # Rileva automaticamente il delimitatore
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                # Normalizza nomi colonne (rimuovi spazi, lowercase)
                fieldnames = reader.fieldnames
                if not fieldnames:
                    print("❌ File CSV vuoto o senza intestazioni")
                    return []
                
                # Mappa possibili nomi colonne
                column_mapping = {}
                for field in fieldnames:
                    clean_field = field.strip().lower().replace(' ', '_')
                    if 'reporter' in clean_field and 'id' in clean_field:
                        column_mapping['reporter_id'] = field
                    elif 'reported' in clean_field and 'id' in clean_field:
                        column_mapping['reported_id'] = field
                    elif 'nickname' in clean_field or ('reported' in clean_field and 'name' in clean_field):
                        column_mapping['reported_nickname'] = field
                
                if len(column_mapping) < 3:
                    print(f"❌ Colonne richieste non trovate nel CSV")
                    print(f"📋 Colonne disponibili: {fieldnames}")
                    print(f"📋 Colonne trovate: {column_mapping}")
                    return []
                
                for row in reader:
                    try:
                        reporter_id = str(row[column_mapping['reporter_id']]).strip()
                        reported_id = str(row[column_mapping['reported_id']]).strip()
                        reported_nickname = str(row[column_mapping['reported_nickname']]).strip()
                        
                        if reporter_id and reported_id:
                            reports.append({
                                'reporter_id': reporter_id,
                                'reported_id': reported_id,
                                'reported_nickname': reported_nickname
                            })
                    except (KeyError, ValueError) as e:
                        self.logger.warning(f"⚠️ Riga CSV saltata: {e}")
                        continue
            
            print(f"🔍 Trovate {len(reports)} segnalazioni nel file CSV")
            return reports
            
        except Exception as e:
            self.logger.error(f"❌ Errore parsing file CSV: {e}")
            print(f"❌ Errore parsing CSV: {e}")
            return []
    
    def _parse_text_reports(self, filepath: Path) -> List[Dict]:
        """Parse file testo segnalazioni (formato playerReports.log)"""
        try:
            reports = []
            
            # Prova diversi encoding
            content = None
            for encoding in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"📄 File letto con encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print("❌ Impossibile leggere il file con nessun encoding supportato")
                return []
            
            # Pattern per il formato: 
            # ===== PLAYER M2535440280010631 HAS REPORTED P976198437253697453 (NICKNAME: N_Rostappen88) FOR BAD BEHAVIOR =====
            pattern = r'===== PLAYER (\w+) HAS REPORTED (\w+) \(NICKNAME: ([^)]+)\) FOR BAD BEHAVIOR ====='
            
            matches = re.findall(pattern, content)
            
            print(f"🔍 Trovate {len(matches)} segnalazioni nel file")
            
            for match in matches:
                reporter_id = match[0].strip()
                reported_id = match[1].strip()
                reported_nickname = match[2].strip()
                
                reports.append({
                    'reporter_id': reporter_id,
                    'reported_id': reported_id,
                    'reported_nickname': reported_nickname
                })
                
                print(f"  📝 {reporter_id} -> {reported_id} ({reported_nickname})")
            
            return reports
            
        except Exception as e:
            self.logger.error(f"❌ Errore parsing file testo: {e}")
            print(f"❌ Errore parsing file testo: {e}")
            return []
    
    def _process_bad_driver_reports(self, reports_data: List[Dict], source_file: str):
        """Processa e salva segnalazioni nel database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n📊 Processando {len(reports_data)} segnalazioni...")
            
            imported = 0
            skipped = 0
            errors = 0
            
            for report in reports_data:
                try:
                    reporter_id = report.get('reporter_id', '').strip()
                    reported_id = report.get('reported_id', '').strip()
                    reported_nickname = report.get('reported_nickname', '').strip()
                    
                    if not reporter_id or not reported_id:
                        skipped += 1
                        continue
                    
                    # Ottieni nomi dai drivers
                    cursor.execute('SELECT last_name FROM drivers WHERE driver_id = ?', (reporter_id,))
                    reporter_result = cursor.fetchone()
                    reporter_name = reporter_result[0] if reporter_result else None
                    
                    cursor.execute('SELECT last_name FROM drivers WHERE driver_id = ?', (reported_id,))
                    reported_result = cursor.fetchone()
                    reported_name = reported_result[0] if reported_result else None
                    
                    # Inserisci segnalazione (UNIQUE constraint previene duplicati)
                    cursor.execute('''
                        INSERT OR IGNORE INTO bad_driver_reports 
                        (reporter_id, reporter_name, reported_id, reported_nickname, 
                         reported_name, source_file)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (reporter_id, reporter_name, reported_id, reported_nickname, 
                          reported_name, source_file))
                    
                    if cursor.rowcount > 0:
                        imported += 1
                    else:
                        skipped += 1  # Già esistente
                        
                except Exception as e:
                    self.logger.error(f"❌ Errore processando segnalazione: {e}")
                    errors += 1
            
            # Aggiorna contatori bad_driver_reports nei piloti
            print("\n🔄 Aggiornamento contatori bad driver...")
            updated_drivers = self._update_bad_driver_counters(cursor)
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ IMPORT SEGNALAZIONI COMPLETATO")
            print(f"➕ Segnalazioni importate: {imported}")
            print(f"⏭️  Segnalazioni saltate: {skipped}")
            print(f"❌ Errori: {errors}")
            print(f"🔄 Piloti aggiornati: {updated_drivers}")
            
        except Exception as e:
            self.logger.error(f"❌ Errore processamento segnalazioni: {e}")
            print(f"❌ Errore durante processamento: {e}")
    
    def _update_bad_driver_counters(self, cursor) -> int:
        """Aggiorna i contatori bad_driver_reports per ogni pilota"""
        try:
            # Calcola segnalazioni uniche per ogni pilota segnalato
            cursor.execute('''
                SELECT reported_id, COUNT(DISTINCT reporter_id) as unique_reports
                FROM bad_driver_reports
                GROUP BY reported_id
            ''')
            
            report_counts = cursor.fetchall()
            updated_count = 0
            
            for reported_id, unique_reports in report_counts:
                cursor.execute('''
                    UPDATE drivers 
                    SET bad_driver_reports = ?
                    WHERE driver_id = ?
                ''', (unique_reports, reported_id))
                
                if cursor.rowcount > 0:
                    updated_count += 1
            
            return updated_count
            
        except Exception as e:
            self.logger.error(f"❌ Errore aggiornamento contatori: {e}")
            return 0
    
    def show_bad_driver_statistics(self):
        """Mostra statistiche segnalazioni bad driver"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*60}")
            print(f"🚨 STATISTICHE BAD DRIVER")
            print(f"{'='*60}")
            
            # Statistiche generali
            cursor.execute('SELECT COUNT(*) FROM bad_driver_reports')
            total_reports = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT reported_id) FROM bad_driver_reports')
            unique_reported = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT reporter_id) FROM bad_driver_reports')
            unique_reporters = cursor.fetchone()[0]
            
            print(f"\n📊 STATISTICHE GENERALI:")
            print(f"  • Segnalazioni totali: {total_reports}")
            print(f"  • Piloti segnalati: {unique_reported}")
            print(f"  • Piloti che hanno segnalato: {unique_reporters}")
            
            # Top piloti segnalati
            max_reports = self.config['bad_driver']['max_reports_for_warning']
            
            cursor.execute('''
                SELECT d.driver_id, d.last_name, d.bad_driver_reports,
                       COUNT(bdr.id) as total_individual_reports
                FROM drivers d
                LEFT JOIN bad_driver_reports bdr ON d.driver_id = bdr.reported_id
                WHERE d.bad_driver_reports > 0
                GROUP BY d.driver_id
                ORDER BY d.bad_driver_reports DESC
                LIMIT 10
            ''')
            
            top_reported = cursor.fetchall()
            
            if top_reported:
                print(f"\n🔥 TOP PILOTI SEGNALATI:")
                print(f"{'Nome':<25} {'Segnalazioni':<12} {'Dettaglio':<15} {'Stato':<15}")
                print("-" * 70)
                
                for driver_id, name, unique_reports, total_reports in top_reported:
                    status = "⚠️ BAD DRIVER" if unique_reports > max_reports else "🟡 Attenzione"
                    print(f"{name:<25} {unique_reports:<12} ({total_reports} totali)    {status:<15}")
            
            # Piloti che segnalano di più
            cursor.execute('''
                SELECT d.last_name, COUNT(bdr.id) as reports_made
                FROM drivers d
                JOIN bad_driver_reports bdr ON d.driver_id = bdr.reporter_id
                GROUP BY d.driver_id
                ORDER BY reports_made DESC
                LIMIT 5
            ''')
            
            top_reporters = cursor.fetchall()
            
            if top_reporters:
                print(f"\n👮 TOP SEGNALATORI:")
                for name, reports in top_reporters:
                    print(f"  • {name}: {reports} segnalazioni")
            
            # Statistiche per fonte file
            cursor.execute('''
                SELECT source_file, COUNT(*) as count
                FROM bad_driver_reports
                GROUP BY source_file
                ORDER BY count DESC
            ''')
            
            sources = cursor.fetchall()
            
            if sources:
                print(f"\n📁 STATISTICHE PER FONTE:")
                for source, count in sources:
                    print(f"  • {source}: {count} segnalazioni")
            
            # Trend segnalazioni
            cursor.execute('''
                SELECT DATE(created_at) as date, COUNT(*) as daily_reports
                FROM bad_driver_reports
                WHERE created_at >= DATE('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 10
            ''')
            
            daily_trends = cursor.fetchall()
            
            if daily_trends:
                print(f"\n📈 TREND ULTIMI 10 GIORNI:")
                for date, count in daily_trends:
                    print(f"  • {date}: {count} segnalazioni")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione statistiche: {e}")
            print(f"❌ Errore durante visualizzazione statistiche: {e}")


def main():
    """Funzione principale per esecuzione standalone"""
    try:
        # Verifica se il file di configurazione esiste
        if not Path("acc_config.json").exists():
            print("⚠️  File config non trovato: /home/utente/acc/ACCSM Backup/acc_config.json")
        
        # Verifica database
        if not Path("acc_stats.db").exists():
            print("❌ Database non trovato: /home/utente/acc/ACCSM Backup/acc_stats.db")
            return
        
        # Inizializza manager
        manager = BadDriverManager()
        
        # Mostra menu
        manager.show_menu()
        
    except Exception as e:
        print(f"❌ Errore durante l'inizializzazione: {e}")
        return


if __name__ == "__main__":
    main()