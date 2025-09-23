#!/usr/bin/env python3
"""
ACCSM - ACC Server Manager
Modulo principale per inizializzazione e gestione del sistema

Questo modulo si occupa di:
- Creazione del database SQLite 
- Creazione del file di configurazione
- Menu principale per l'esecuzione di tutti i moduli
"""

import json
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


class ACCSystemInitializer:
    """Classe per l'inizializzazione del sistema ACCSM"""
    
    def __init__(self, config_file='acc_config.json'):
        """Inizializza il sistema di gestione ACC"""
        self.config_file = config_file
        self.config = None
        self.db_path = None
        
    def load_or_create_config(self) -> dict:
        """Carica o crea file di configurazione"""
        if Path(self.config_file).exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Template configurazione
            template = {
                "community": {
                    "name": "Your Community Name",
                    "description": "Your community description"
                },
                "social": {
                    "discord": "https://discord.gg/your-discord-link",
                    "simgrid": "https://simgrid.gg/your-simgrid-link"
                },
                "database": {
                    "path": "acc_stats.db"
                },
                "dashboard": {
                     "url": "https://your-app.streamlit.app"
                },
                "paths": {
                    "logs": "./logs",
                    "local_results": "./acc_results",
                    "import_export_entrylist": "./entrylist",
                    "bad_players": "./bad_players",
                    "remote_backup": "/backup",
                    "db_backups": "./db_backups"
                },
                "ftp": {
                    "host": "your-gportal-server.com",
                    "port": 21,
                    "user": "your_username",
                    "password": "your_password",
                    "remote_results_path": "/gameserver/acc/results",
                    "delete_after_sync": False,
                    "backup_before_delete": True
                },
                "file_processing": {
                    "max_retries": 3,
                    "retry_delay": 2,
                    "backup_existing": True,
                    "extensions": [".json"],
                    "auto_detect_competition": True
                },
                "competition": {
                    "championship_id": 1,
                    "track_name": "Auto-detect from JSON",
                    "weekend_format": "sprint"
                },
                "github": {
                    "username": "your_github_username",
                    "password": "your_github_token",
                    "repository": "your_repository_name",
                    "db_path_in_repo": "database/acc_stats.db",
                    "branch": "main"
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=4)
            
            print(f"✅ Creato file di configurazione: {self.config_file}")
            print("🔧 Modifica il file acc_config.json con i tuoi parametri")
            return template

    def init_database(self):
        """Inizializza il database con schema completo - VERSIONE AGGIORNATA CON GERARCHIA E BAD DRIVER"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabella campionati
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS championships (
                    championship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    season INTEGER,                        -- Es: 2025, 2026
                    start_date DATE,
                    end_date DATE,
                    total_rounds INTEGER,
                    is_completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Nuova tabella competizioni/round
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitions (
                    competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    championship_id INTEGER,
                    name TEXT NOT NULL,                    -- "Round 1", "Gara di Monza"
                    round_number INTEGER,                  -- 1, 2, 3...
                    track_name TEXT NOT NULL,
                    date_start DATE,
                    date_end DATE,
                    weekend_format TEXT,                   -- "sprint", "standard", "endurance"
                    points_system TEXT,                    -- non utilizzato al momento
                    points_system_json TEXT,               -- JSON con sistema punti per questa competizione  
                    is_completed BOOLEAN DEFAULT FALSE,
                    points_awarded BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (championship_id) REFERENCES championships (championship_id)
                )
            ''')

            # Tabella per risultati aggregati per competizione (solo totali)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competition_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    -- Punti aggregati da tutte le sessioni
                    race_points INTEGER DEFAULT 0,             -- Somma punti da tutte le gare (R1+R2+...)
                    pole_points INTEGER DEFAULT 0,             -- Punti pole position (dalle qualifiche)
                    fastest_lap_points INTEGER DEFAULT 0,      -- Punti giri veloci (da tutte le sessioni)
                    bonus_points INTEGER DEFAULT 0,            -- Punti bonus assegnati
                    penalty_points INTEGER DEFAULT 0,          -- Punti penalità (sottratti)
                    total_points INTEGER DEFAULT 0,            -- Totale finale
                    -- Metadati
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    -- Vincoli
                    FOREIGN KEY (competition_id) REFERENCES competitions (competition_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id),
                    UNIQUE(competition_id, driver_id)
                )
            ''')

            # Tabella per risultati dettagliati per sessione
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competition_session_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,               -- Riferimento alla sessione specifica
                    session_type TEXT NOT NULL,             -- 'R1', 'R2', 'Q1', 'Q2', 'FP1', etc.
                    position INTEGER,                       -- Posizione finale in questa sessione
                    points INTEGER DEFAULT 0,               -- Punti ottenuti in questa specifica sessione
                    best_lap_time INTEGER,                  -- Miglior tempo giro in questa sessione
                    total_laps INTEGER DEFAULT 0,           -- Giri completati in questa sessione
                    is_classified BOOLEAN DEFAULT TRUE,     -- Se il pilota è classificato in questa sessione
                    -- Metadati
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    -- Vincoli
                    FOREIGN KEY (competition_id) REFERENCES competitions (competition_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id),
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    UNIQUE(competition_id, driver_id, session_id)
                )
            ''')

            # Nuova tabella sistema punti
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS points_systems (
                    system_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,             
                    description TEXT,
                    position_points_json TEXT NOT NULL,    
                    pole_position_points INTEGER DEFAULT 0,
                    fastest_lap_points INTEGER DEFAULT 0,
                    minimum_classified_percentage REAL DEFAULT 70.0, 
                    points_for_unclassified BOOLEAN DEFAULT FALSE,   
                    drop_worst_results INTEGER DEFAULT 0,            
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Nuova tabella penalità manuali      
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS manual_penalties (
                    penalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    championship_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    competition_id INTEGER,               
                    
                    penalty_points INTEGER NOT NULL,     
                    reason TEXT NOT NULL,                
                    applied_by TEXT,                     
                    applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    is_active BOOLEAN DEFAULT TRUE,      
                    notes TEXT,
                    
                    FOREIGN KEY (championship_id) REFERENCES championships (championship_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id),
                    FOREIGN KEY (competition_id) REFERENCES competitions (competition_id)
                )
            ''')            

            # Nuova tabella classifiche campionati  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS championship_standings (
                    championship_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                        
                    total_points INTEGER DEFAULT 0,
                    position INTEGER,
                        
                    competitions_participated INTEGER DEFAULT 0,  
                    wins INTEGER DEFAULT 0,                       
                    podiums INTEGER DEFAULT 0,                    
                    poles INTEGER DEFAULT 0,                      
                    fastest_laps INTEGER DEFAULT 0,              
                    points_dropped INTEGER DEFAULT 0,            
                        
                    average_position REAL,                       
                    best_position INTEGER,                       
                    consistency_rating REAL,                     
                        
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                    PRIMARY KEY (championship_id, driver_id),
                    FOREIGN KEY (championship_id) REFERENCES championships (championship_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id)
                )
            ''')

            # Tabella piloti (invariata)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drivers (
                    driver_id TEXT PRIMARY KEY,
                    last_name TEXT NOT NULL,
                    short_name TEXT,
                    preferred_race_number INTEGER,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    total_sessions INTEGER DEFAULT 0,
                    bad_driver_reports INTEGER DEFAULT 0,
                    trust_level INTEGER DEFAULT 0 CHECK (trust_level IN (0, 1, 2))
                )
            ''')
            
            # Tabella sessioni - MODIFICATA: rimosso championship_id, aggiunto competition_id
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    session_type TEXT NOT NULL,
                    track_name TEXT NOT NULL,
                    server_name TEXT,
                    session_date TIMESTAMP NOT NULL,
                    best_lap_overall INTEGER,
                    total_drivers INTEGER,
                    competition_id INTEGER,                -- NUOVO: collegamento a competitions
                    session_order INTEGER,                 -- NUOVO: ordine sessione nel weekend (1=FP, 2=Q1, 3=R1, etc)
                    is_autoassign_comp BOOLEAN DEFAULT TRUE,      -- NUOVO: distingue sessioni ufficiali da test
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (competition_id) REFERENCES competitions (competition_id)
                )
            ''')
            
            # Tabella risultati sessioni (invariata)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    driver_id TEXT NOT NULL,
                    position INTEGER,
                    car_id INTEGER,
                    race_number INTEGER,
                    car_model INTEGER,
                    best_lap INTEGER,
                    total_time INTEGER,
                    lap_count INTEGER,
                    is_spectator BOOLEAN DEFAULT FALSE,
                    points_awarded INTEGER DEFAULT 0,      -- NUOVO: punti assegnati
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id)
                )
            ''')
            
            # Tabella giri (invariata)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS laps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    driver_id TEXT NOT NULL,
                    car_id INTEGER NOT NULL,
                    lap_time INTEGER NOT NULL,
                    is_valid_for_best BOOLEAN,
                    split1 INTEGER,
                    split2 INTEGER,
                    split3 INTEGER,
                    lap_number INTEGER,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id)
                )
            ''')
            
            # Tabella penalità (invariata)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS penalties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    driver_id TEXT NOT NULL,
                    car_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    penalty_type TEXT NOT NULL,
                    penalty_value INTEGER,
                    violation_lap INTEGER,
                    cleared_lap INTEGER,
                    is_post_race BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id)
                )
            ''')
            
            # NUOVA TABELLA per segnalazioni bad driver
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bad_driver_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id TEXT NOT NULL,              -- ID di chi ha segnalato
                    reporter_name TEXT,                     -- Nome di chi ha segnalato (cache)
                    reported_id TEXT NOT NULL,              -- ID di chi è stato segnalato
                    reported_nickname TEXT,                 -- Nickname di chi è stato segnalato (dal file)
                    reported_name TEXT,                     -- Nome di chi è stato segnalato (cache)
                    report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_file TEXT,                       -- File da cui proviene la segnalazione
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reporter_id) REFERENCES drivers (driver_id),
                    FOREIGN KEY (reported_id) REFERENCES drivers (driver_id),
                    UNIQUE(reporter_id, reported_id)        -- Un pilota può segnalare un altro solo una volta
                )
            ''')
            
            # Tabella file sincronizzati (invariata)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS synced_files (
                    filename TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER,
                    remote_path TEXT,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted_from_server BOOLEAN DEFAULT FALSE,
                    backup_created BOOLEAN DEFAULT FALSE,
                    session_info TEXT,
                    processed_in_db BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP,
                    processing_result TEXT
                )
            ''')
            
            # Indici per performance - AGGIORNATI CON BAD DRIVER
            indices = [
                'CREATE INDEX IF NOT EXISTS idx_driver_sessions ON session_results(driver_id)',
                'CREATE INDEX IF NOT EXISTS idx_session_type ON sessions(session_type)',
                'CREATE INDEX IF NOT EXISTS idx_track_name ON sessions(track_name)',
                'CREATE INDEX IF NOT EXISTS idx_best_laps ON laps(is_valid_for_best, lap_time)',
                'CREATE INDEX IF NOT EXISTS idx_competition_sessions ON sessions(competition_id)',     # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_championship_competitions ON competitions(championship_id)',  # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_championship_standings ON championship_standings(championship_id, total_points DESC)',  # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_bad_reports_reporter ON bad_driver_reports(reporter_id)',  # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_bad_reports_reported ON bad_driver_reports(reported_id)',  # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_driver_trust ON drivers(trust_level)',
                'CREATE INDEX IF NOT EXISTS idx_driver_reports ON drivers(bad_driver_reports)',
                'CREATE INDEX IF NOT EXISTS idx_session_date ON sessions(session_date)',              # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_competition_round ON competitions(championship_id, round_number)',  # NUOVO
                'CREATE INDEX IF NOT EXISTS idx_competition_results_competition ON competition_results(competition_id)',
                'CREATE INDEX IF NOT EXISTS idx_competition_results_driver ON competition_results(driver_id)',
                'CREATE INDEX IF NOT EXISTS idx_competition_results_points ON competition_results(total_points DESC)',
                'CREATE INDEX IF NOT EXISTS idx_championship_standings_points ON championship_standings(championship_id, total_points DESC)',
                'CREATE INDEX IF NOT EXISTS idx_championship_standings_position ON championship_standings(championship_id, position)',
                'CREATE INDEX IF NOT EXISTS idx_manual_penalties_championship ON manual_penalties(championship_id)',
                'CREATE INDEX IF NOT EXISTS idx_manual_penalties_driver ON manual_penalties(driver_id)',
                'CREATE INDEX IF NOT EXISTS idx_points_systems_active ON points_systems(is_active)',
                'CREATE INDEX IF NOT EXISTS idx_competitions_points_system ON competitions(points_system_json)'
            ]
            
            for index in indices:
                cursor.execute(index)
                
            # Inserimento sistemi punti predefiniti
            systems = [
                ('F1 Standard', 'Sistema punti Formula 1 standard', 
                 '{"1": 25, "2": 18, "3": 15, "4": 12, "5": 10, "6": 8, "7": 6, "8": 4, "9": 2, "10": 1}', 
                 0, 1, 0),
                ('F1 Sprint', 'Sistema punti Formula 1 per gare sprint', 
                 '{"1": 8, "2": 7, "3": 6, "4": 5, "5": 4, "6": 3, "7": 2, "8": 1}', 
                 0, 0, 0),
                ('GT3 Standard', 'Sistema punti GT3 standard', 
                 '{"1": 20, "2": 15, "3": 12, "4": 10, "5": 8, "6": 6, "7": 4, "8": 3, "9": 2, "10": 1}', 
                 1, 1, 0),
                ('GT3 Drop 2', 'Sistema GT3 con scarto 2 peggiori risultati', 
                 '{"1": 20, "2": 15, "3": 12, "4": 10, "5": 8, "6": 6, "7": 4, "8": 3, "9": 2, "10": 1}', 
                 1, 1, 2),
                ('Endurance', 'Sistema punti gare endurance', 
                 '{"1": 30, "2": 24, "3": 20, "4": 16, "5": 13, "6": 11, "7": 9, "8": 7, "9": 5, "10": 3, "11": 2, "12": 1}', 
                 2, 2, 0),
                ('Custom Configurabile', 'Sistema personalizzabile - modificare position_points_json', 
                 '{"1": 20, "2": 19, "3": 18, "4": 17, "5": 16, "6": 15, "7": 14, "8": 13, "9": 12, "10": 11, "11": 10, "12": 9, "13": 8, "14": 7, "15": 6, "16": 5, "17": 4, "18": 3, "19": 2, "20": 1}',
                 0, 0, 0)
                      ]
        
            inserted_count = 0
            for name, desc, points_json, pole_pts, fast_pts, drop_results in systems:
                cursor.execute('''
                    INSERT OR IGNORE INTO points_systems 
                    (name, description, position_points_json, pole_position_points, fastest_lap_points, drop_worst_results)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, desc, points_json, pole_pts, fast_pts, drop_results))
                if cursor.rowcount > 0:
                    inserted_count += 1
            
            conn.commit()
            conn.close()
            print(f"✅ Database inizializzato correttamente - Inseriti {inserted_count} sistemi punti")
            
        except Exception as e:
            print(f"❌ Errore inizializzazione database: {e}")
            raise

    def initialize_system(self, silent=False):
        """Inizializza completamente il sistema ACCSM se necessario"""
        config_exists = Path(self.config_file).exists()
        
        if not config_exists:
            if not silent:
                print("🚀 Inizializzazione sistema ACCSM...")
            # Carica o crea configurazione
            self.config = self.load_or_create_config()
        else:
            # Carica configurazione esistente
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        
        self.db_path = self.config['database']['path']
        db_exists = Path(self.db_path).exists()
        
        if not db_exists:
            if not silent:
                print(f"🔧 Creazione database: {self.db_path}")
            # Crea solo directory essenziali per l'inizializzazione
            essential_dirs = ['logs', 'local_results', 'db_backups']
            for dir_key in essential_dirs:
                if dir_key in self.config['paths']:
                    Path(self.config['paths'][dir_key]).mkdir(parents=True, exist_ok=True)
            
            # Inizializza database
            self.init_database()
        
        if not silent and (not config_exists or not db_exists):
            print("✅ Sistema ACCSM inizializzato correttamente!")
        
        return True


class ACCMainMenu:
    """Menu principale per l'esecuzione dei moduli ACCSM"""
    
    def __init__(self):
        self.modules = {
            '1': {
                'name': 'Manager ACC Server',
                'file': 'manager_acc.py'
            },
            '2': {
                'name': 'Gestione Competizioni',
                'file': 'competitions_acc.py'
            },
            '3': {
                'name': 'Classifiche',
                'file': 'standings_acc.py'
            },
            '4': {
                'name': 'Gestione Piloti',
                'file': 'driver_acc.py'
            },
            '5': {
                'name': 'Entry List',
                'file': 'entrylist_acc.py'
            },
            '6': {
                'name': 'Report',
                'file': 'report_acc.py'
            },
            '7': {
                'name': 'Report Mobile',
                'file': 'mreport_acc.py'
            },
            '8': {
                'name': 'Dashboard',
                'file': 'dashboard_acc.py'
            },
            '9': {
                'name': 'Pulizia Sistema',
                'file': 'clean_acc.py'
            }
        }
    
    def check_system_requirements(self) -> bool:
        """Verifica che il sistema sia inizializzato"""
        config_exists = Path('acc_config.json').exists()
        db_exists = Path('acc_stats.db').exists()
        
        if not config_exists:
            print("⚠️  File di configurazione non trovato")
            print("Inizializzare il sistema prima di continuare")
            return False
            
        if not db_exists:
            print("❌ Database non trovato")  
            print("Inizializzare il sistema prima di continuare")
            return False
            
        return True
    
    def display_menu(self):
        """Visualizza il menu principale"""
        print("\n" + "="*50)
        print("🏁 ACCSM - ACC Server Manager")
        print("="*50)
        
        for key, module in self.modules.items():
            print(f"{key}. {module['name']}")
        
        print(f"0. Esci")
        print("="*50)
    
    def run_module(self, module_file: str) -> bool:
        """Esegue un modulo Python"""
        try:
            if not Path(module_file).exists():
                print(f"❌ File non trovato: {module_file}")
                return False
            
            print(f"\n🚀 Avvio {module_file}...")
            
            # Gestione speciale per dashboard Streamlit
            if module_file == 'dashboard_acc.py':
                print("📊 Avvio dashboard Streamlit...")
                print("🌐 La dashboard si aprirà automaticamente nel browser")
                print("⏹️  Premi Ctrl+C per fermare il server")
                result = subprocess.run(['streamlit', 'run', module_file], check=True)
            else:
                result = subprocess.run([sys.executable, module_file], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Errore esecuzione {module_file}: {e}")
            return False
        except KeyboardInterrupt:
            print(f"\n⏹️  Esecuzione {module_file} interrotta dall'utente")
            return True
        except Exception as e:
            print(f"❌ Errore generico esecuzione {module_file}: {e}")
            return False
    
    def run(self):
        """Esegue il menu principale"""
        # Inizializzazione automatica all'avvio
        initializer = ACCSystemInitializer()
        try:
            initializer.initialize_system(silent=True)
        except Exception as e:
            print(f"❌ Errore inizializzazione: {e}")
            return
        
        while True:
            self.display_menu()
            
            choice = input("\n➤ Seleziona opzione: ").strip()
            
            if choice == '0':
                print("\n👋 Arrivederci!")
                break
            elif choice in self.modules:
                if not self.check_system_requirements():
                    input("\n⚠️  Premi INVIO per continuare...")
                    continue
                
                module = self.modules[choice]
                success = self.run_module(module['file'])
                
                if success:
                    input(f"\n✅ {module['name']} completato. Premi INVIO per continuare...")
                else:
                    input(f"\n❌ Errore in {module['name']}. Premi INVIO per continuare...")
            else:
                print(f"\n❌ Opzione non valida: {choice}")
                input("⚠️  Premi INVIO per continuare...")


def main():
    """Funzione principale"""
    try:
        menu = ACCMainMenu()
        menu.run()
    except KeyboardInterrupt:
        print("\n\n⏹️  Programma interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ Errore generico: {e}")


if __name__ == "__main__":
    main()