#!/usr/bin/env python3
"""
ACC Server Manager - Gestione e Sincronizzazione
Gestione completa per server Assetto Corsa Competizione
"""
import sqlite3
import json
import ftplib
import hashlib
import logging
import re
import shutil
import requests
import base64
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class AutoModeManager:
    """Gestione modalità automatica per ACC Server Manager"""
    
    def __init__(self, acc_manager):
        self.acc_manager = acc_manager
        self.is_running = False
        self.auto_thread = None
        self.interval_seconds = 15 * 60  # 15 minuti
        
    def start_auto_mode(self):
        """Avvia modalità automatica"""
        if self.is_running:
            print("⚠️ Modalità automatica già in esecuzione")
            return
        
        self.is_running = True
        print(f"\n🤖 MODALITÀ AUTOMATICA AVVIATA")
        print(f"⏰ Esecuzione ogni {self.interval_seconds // 60} minuti")
        print(f"🔄 Funzione: Sync + Load + GitHub + Classifiche")
        print(f"⏹️  Usa l'opzione 5.2 per fermare\n")
        
        # Esegui subito la prima volta
        self._execute_sync_and_load()
        
        # Avvia thread per esecuzioni periodiche
        self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self.auto_thread.start()
        
        print("✅ Modalità automatica avviata in background")
        print("💡 Puoi continuare a usare il menu normalmente")
    
    def stop_auto_mode(self):
        """Ferma modalità automatica"""
        if not self.is_running:
            return
        
        print(f"\n🛑 Arresto modalità automatica...")
        self.is_running = False
        
        if self.auto_thread and self.auto_thread.is_alive():
            self.auto_thread.join(timeout=5)
        
        print("✅ Modalità automatica fermata")
    
    def _auto_loop(self):
        """Loop automatico per esecuzioni periodiche"""
        while self.is_running:
            # Attendi per l'intervallo specificato
            for _ in range(self.interval_seconds):
                if not self.is_running:
                    return
                time.sleep(1)
            
            # Esegui sync and load
            if self.is_running:
                self._execute_sync_and_load()
    
    def _execute_sync_and_load(self):
        """Esegue sync + load + GitHub con gestione errori"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{'='*60}")
        print(f"🔄 ESECUZIONE AUTOMATICA - {timestamp}")
        print(f"{'='*60}")
        
        try:
            # Esegui la funzione 4 del menu (sync_and_load) - ora non-interattiva
            self.acc_manager.sync_and_load()
            
            print(f"✅ Esecuzione completata alle {datetime.now().strftime('%H:%M:%S')}")

            # Controlla sessioni processate di recente per calcolare classifiche
            self._check_and_calculate_standings()

            # NUOVO: Wake up dashboard
            self._wake_up_dashboard()
            
        except Exception as e:
            print(f"❌ Errore durante esecuzione automatica: {e}")
            self.acc_manager.logger.error(f"Errore modalità automatica: {e}")
        
        # Calcola prossima esecuzione
        next_run = datetime.now() + timedelta(seconds=self.interval_seconds)
        next_run = next_run.replace(second=0, microsecond=0)
        
        print(f"⏰ Prossima esecuzione: {next_run.strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")

        # NUOVO: Mostra di nuovo il menu automatico
        print(f"\n🤖 MODALITÀ AUTOMATICA ATTIVA")
        print(f"📋 Opzioni disponibili:")
        print("  2. Ferma modalità automatica")
        print("  3. Cambia intervallo") 
        print("  0. Torna al menu principale")
        print("\nScelta: ", end="", flush=True)

    def _wake_up_dashboard(self):
        """Sveglia la dashboard con un semplice ping HTTP"""
        try:
            # Ottieni URL dashboard dalla configurazione
            dashboard_url = self.acc_manager.config.get('dashboard', {}).get('url')
            
            if not dashboard_url:
                print("ℹ️  URL dashboard non configurato, skip wake up")
                return
            
            print(f"\n🌐 WAKE UP DASHBOARD")
            print(f"📡 Ping: {dashboard_url}")
            
            # Semplice richiesta GET per svegliare l'app
            response = requests.get(
                dashboard_url,
                timeout=30,  # Timeout generoso per wake up
                headers={
                    'User-Agent': 'ACC-Server-Manager-AutoMode/1.0',
                    'Cache-Control': 'no-cache'
                }
            )
            
            if response.status_code == 200:
                print("✅ Dashboard svegliata con successo")
                # Piccola pausa per permettere alla dashboard di caricare i nuovi dati
                time.sleep(5)
            else:
                print(f"⚠️  Dashboard response: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("⏰ Timeout durante wake up (normale se l'app era in sleep)")
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore wake up dashboard: {e}")
        except Exception as e:
            print(f"❌ Errore generico wake up: {e}")
            self.acc_manager.logger.error(f"Errore wake up dashboard: {e}")
    
    def _check_and_calculate_standings(self):
        """Controlla sessioni processate di recente e calcola classifiche se necessario"""
        try:
            print(f"\n🏆 CONTROLLO CLASSIFICHE")
            
            # Calcola timestamp di riferimento (ultima esecuzione - 10 minuti di margine)
            time_threshold = datetime.now() - timedelta(seconds=self.interval_seconds + 600)  # +10 minuti margine
            
            # Query per trovare sessioni processate di recente
            import sqlite3
            conn = sqlite3.connect(self.acc_manager.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT c.competition_id, c.championship_id
                FROM sessions s
                JOIN competitions c ON s.competition_id = c.competition_id
                WHERE s.competition_id IS NOT NULL
                AND c.is_completed = 0
                AND s.processed_at > ?
            ''', (time_threshold.strftime('%Y-%m-%d %H:%M:%S'),))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                print("ℹ️  Nessuna sessione recente da elaborare")
                return
            
            print(f"📊 Trovate {len(results)} competizioni con sessioni recenti")
            
            # Importa championship manager
            from standings_acc import ChampionshipManager
            standings_manager = ChampionshipManager(self.acc_manager.config_file)
            
            for competition_id, championship_id in results:
                # Calcola risultati competizione
                print(f"🏁 Calcolo risultati competizione {competition_id}")
                standings_manager.calculate_competition_results(competition_id)
                
                # Calcola classifiche campionato se presente
                if championship_id:
                    print(f"🏆 Calcolo classifiche campionato {championship_id}")
                    standings_manager.calculate_championship_standings(championship_id)
            
            championships_count = len([r for r in results if r[1] is not None])
            print(f"✅ Classifiche aggiornate: {len(results)} competizioni, {championships_count} campionati")
            
        except Exception as e:
            print(f"❌ Errore calcolo classifiche: {e}")
            self.acc_manager.logger.error(f"Errore calcolo classifiche automatico: {e}")

class ACCServerManager:
    """Classe principale per la gestione del server ACC"""
    
    def __init__(self, config_file='acc_config.json'):
        """Inizializza il manager con configurazione"""
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_logging()
        self.db_path = self.config['database']['path']
        self.check_database()
        self.auto_mode = AutoModeManager(self)       

    def load_config(self) -> dict:
        """Carica configurazione da file"""
        try:
            if not Path(self.config_file).exists():
                print(f"⚠️  File config non trovato: {Path.cwd() / self.config_file}")
                print("Esegui prima il main_acc.py per inizializzare il sistema")
                exit(1)
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Errore parsing configurazione: {e}")
            exit(1)
        except Exception as e:
            print(f"❌ Errore caricamento configurazione: {e}")
            exit(1)
    
    def setup_logging(self):
        """Configura il sistema di logging"""
        log_dir = Path(self.config['paths']['logs'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"acc_manager_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🏁 ACC Server Manager avviato - Community: {self.config['community']['name']}")

    def backup_database(self) -> Optional[str]:
        """Crea backup del database con timestamp"""
        try:
            if not Path(self.db_path).exists():
                self.logger.warning("⚠️ Database non esiste, skip backup")
                return None
            
            # Crea directory backup
            backup_dir = Path(self.config['paths']['db_backups'])
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Nome file backup con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"acc_stats_backup_{timestamp}.db"
            backup_path = backup_dir / backup_filename
            
            # Copia file database
            shutil.copy2(self.db_path, backup_path)
            
            # Verifica dimensione
            original_size = Path(self.db_path).stat().st_size
            backup_size = backup_path.stat().st_size
            
            if original_size != backup_size:
                self.logger.error(f"❌ Backup fallito: dimensioni diverse")
                return None
            
            self.logger.info(f"💾 Backup database creato: {backup_filename}")
            print(f"💾 Backup database creato: {backup_filename}")
            
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"❌ Errore backup database: {e}")
            print(f"❌ Errore backup database: {e}")
            return None

    def sync_database_to_github(self):
        """Sincronizza database su GitHub"""
        try:
            print("\n📤 SINCRONIZZAZIONE DATABASE SU GITHUB")
            
            # Verifica configurazione GitHub
            github_config = self.config.get('github', {})
            required_fields = ['username', 'password', 'repository', 'db_path_in_repo']
            
            for field in required_fields:
                if not github_config.get(field):
                    print(f"❌ Configurazione GitHub incompleta: manca '{field}'")
                    return False
            
            if not Path(self.db_path).exists():
                print(f"❌ Database non trovato: {self.db_path}")
                return False
            
            # Leggi file database
            with open(self.db_path, 'rb') as f:
                db_content = f.read()
            
            # Codifica in base64 per GitHub API
            db_base64 = base64.b64encode(db_content).decode('utf-8')
            
            # Prepara richiesta GitHub API
            username = github_config['username']
            token = github_config['password']
            repo = github_config['repository']
            file_path = github_config['db_path_in_repo']
            branch = github_config.get('branch', 'main')
            
            # URL API GitHub
            api_url = f"https://api.github.com/repos/{username}/{repo}/contents/{file_path}"
            
            print(f"📊 Repository: {username}/{repo}")
            print(f"📁 Percorso: {file_path}")
            print(f"🌿 Branch: {branch}")
            print(f"📈 Dimensione DB: {len(db_content):,} bytes")
            
            # Ottieni SHA del file esistente (se presente)
            headers = {'Authorization': f'token {token}'}
            
            print("🔍 Controllo file esistente...")
            get_response = requests.get(api_url, headers=headers)
            
            sha = None
            if get_response.status_code == 200:
                existing_file = get_response.json()
                sha = existing_file['sha']
                print(f"📄 File esistente trovato (SHA: {sha[:8]}...)")
            elif get_response.status_code == 404:
                print("📄 File non esistente, verrà creato")
            else:
                print(f"❌ Errore controllo file esistente: {get_response.status_code}")
                print(f"❌ Risposta: {get_response.text}")
                return False
            
            # Prepara commit message
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_message = f"Update ACC database - {timestamp}"
            
            # Payload per API
            payload = {
                'message': commit_message,
                'content': db_base64,
                'branch': branch
            }
            
            if sha:
                payload['sha'] = sha
            
            # Carica su GitHub
            print("📤 Caricamento in corso...")
            put_response = requests.put(api_url, headers=headers, json=payload)
            
            if put_response.status_code in [200, 201]:
                response_data = put_response.json()
                new_sha = response_data['content']['sha']
                print(f"✅ Database sincronizzato su GitHub")
                print(f"📄 Nuovo SHA: {new_sha[:8]}...")
                print(f"🔗 URL: {response_data['content']['html_url']}")
                
                self.logger.info(f"✅ Database sincronizzato su GitHub: {new_sha}")
                return True
            else:
                print(f"❌ Errore caricamento su GitHub: {put_response.status_code}")
                print(f"❌ Risposta: {put_response.text}")
                self.logger.error(f"❌ Errore GitHub sync: {put_response.status_code} - {put_response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Errore sincronizzazione GitHub: {e}")
            print(f"❌ Errore sincronizzazione GitHub: {e}")
            return False

    def check_database(self):
        """Verifica esistenza database"""
        if not Path(self.db_path).exists():
            print(f"❌ Database non trovato: {self.db_path}")
            print("Esegui prima il main_acc.py per inizializzare il database")
            exit(1)
        
        print(f"✅ Database trovato: {self.db_path}")

    # === SEZIONE FTP ===
    
    def connect_ftp(self) -> ftplib.FTP:
        """Connessione al server FTP"""
        max_retries = self.config['file_processing']['max_retries']
        
        for attempt in range(max_retries):
            try:
                ftp = ftplib.FTP()
                port = self.config['ftp']['port']
                ftp.connect(self.config['ftp']['host'], port, timeout=30)
                ftp.login(self.config['ftp']['user'], self.config['ftp']['password'])
                self.logger.info(f"✅ Connesso a FTP: {self.config['ftp']['host']}:{port}")
                return ftp
            except Exception as e:
                self.logger.warning(f"⚠️ Tentativo {attempt + 1} fallito: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                else:
                    raise Exception(f"❌ Impossibile connettersi dopo {max_retries} tentativi")
    
    def get_file_hash(self, ftp: ftplib.FTP, remote_path: str) -> Optional[str]:
        """Calcola hash del file remoto"""
        try:
            data = []
            ftp.retrbinary(f'RETR {remote_path}', data.append, blocksize=1024)
            file_content = b''.join(data)
            return hashlib.md5(file_content).hexdigest()
        except Exception as e:
            self.logger.error(f"❌ Errore calcolo hash per {remote_path}: {e}")
            return None
    
    def is_result_file(self, filename: str) -> bool:
        """Verifica se il file è un risultato ACC valido"""
        # Pattern ACC: AAMMDD_HHMMSS_X.json dove X = FP/Q/R o FPx/Qx/Rx (x = 1-9)
        acc_pattern = r'^\d{6}_\d{6}_(FP[1-9]?|Q[1-9]?|R[1-9]?)\.json$'
        return bool(re.match(acc_pattern, filename))
    
    def sync_gportal(self, auto_mode=False):
        """Sincronizza file da G-Portal - VERSIONE CORRETTA"""
        try:
            print("\n🔄 SINCRONIZZAZIONE G-PORTAL")
            
        # Conferma cancellazione se abilitata E NON in modalità automatica
            if self.config['ftp']['delete_after_sync'] and not auto_mode:
                print("\n⚠️  ATTENZIONE: Cancellazione file remoti ABILITATA!")
                print(f"📁 Server: {self.config['ftp']['host']}")
                print(f"📂 Path: {self.config['ftp']['remote_results_path']}")
                print(f"💾 Backup: {'SÌ' if self.config['ftp']['backup_before_delete'] else 'NO'}")
                
                confirm = input("\nConfermi? (s/N): ").strip().lower()
                if confirm not in ['s', 'si', 'sì', 'y', 'yes']:
                    print("❌ Operazione annullata")
                    return
            elif self.config['ftp']['delete_after_sync'] and auto_mode:
                # In modalità automatica, procedi senza conferma
                print("🤖 Modalità automatica: cancellazione file abilitata, procedendo...")
            
            ftp = self.connect_ftp()
            
            # Cambia directory
            remote_path = self.config['ftp']['remote_results_path']
            if remote_path:
                ftp.cwd(remote_path)
            
            # Lista file
            file_list = []
            ftp.retrlines('LIST', file_list.append)
            
            # Filtra solo file risultati ACC
            remote_files = []
            for line in file_list:
                parts = line.split()
                if len(parts) >= 9 and line.startswith('-'):
                    filename = ' '.join(parts[8:])
                    if self.is_result_file(filename):
                        size = int(parts[4])
                        remote_files.append({
                            'name': filename,
                            'size': size,
                            'path': f"{remote_path}/{filename}" if remote_path else filename
                        })
            
            if not remote_files:
                print("ℹ️  Nessun file di risultati trovato")
                ftp.quit()
                return
            
            print(f"\n📊 Trovati {len(remote_files)} file di risultati")
            
            # Processa ogni file
            downloaded = 0
            deleted = 0
            
            # CONNESSIONE DATABASE UNICA per tutto il processo
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                for file_info in remote_files:
                    filename = file_info['name']
                    remote_file_path = file_info['path']
                    
                    # Controlla se già sincronizzato
                    cursor.execute('SELECT file_hash FROM synced_files WHERE filename = ?', (filename,))
                    existing = cursor.fetchone()
                    
                    # Calcola hash remoto
                    file_hash = self.get_file_hash(ftp, remote_file_path)
                    if not file_hash:
                        continue
                    
                    # Se già esiste con stesso hash, eventualmente solo cancella
                    if existing and existing[0] == file_hash:
                        if self.config['ftp']['delete_after_sync']:
                            if self.delete_remote_file_with_db(ftp, remote_file_path, filename, cursor):
                                deleted += 1
                        continue
                    
                    # Scarica file
                    local_dir = Path(self.config['paths']['local_results'])
                    local_dir.mkdir(parents=True, exist_ok=True)
                    local_path = local_dir / filename
                    
                    with open(local_path, 'wb') as f:
                        ftp.retrbinary(f'RETR {remote_file_path}', f.write)
                    
                    # Verifica download
                    if local_path.stat().st_size != file_info['size']:
                        self.logger.error(f"❌ Download incompleto: {filename}")
                        continue
                    
                    # Salva in database
                    cursor.execute('''
                        INSERT OR REPLACE INTO synced_files 
                        (filename, file_hash, file_size, remote_path, synced_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (filename, file_hash, file_info['size'], remote_file_path, 
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    
                    downloaded += 1
                    self.logger.info(f"✅ Scaricato: {filename}")
                    
                    # Cancella se richiesto - USA LA STESSA CONNESSIONE DB
                    if self.config['ftp']['delete_after_sync']:
                        if self.delete_remote_file_with_db(ftp, remote_file_path, filename, cursor):
                            deleted += 1
                
                # COMMIT FINALE di tutte le operazioni
                conn.commit()
                
            finally:
                conn.close()
                ftp.quit()
            
            print(f"\n✅ SINCRONIZZAZIONE COMPLETATA")
            print(f"📥 File scaricati: {downloaded}")
            if self.config['ftp']['delete_after_sync']:
                print(f"🗑️  File cancellati: {deleted}")
            
        except Exception as e:
            self.logger.error(f"❌ Errore sincronizzazione: {e}")
    
    def delete_remote_file_with_db(self, ftp: ftplib.FTP, remote_path: str, filename: str, cursor) -> bool:
        """Cancella file remoto con backup opzionale - USA CONNESSIONE DB ESISTENTE"""
        try:
            # Backup se richiesto
            if self.config['ftp']['backup_before_delete']:
                backup_path = self.config['paths']['remote_backup']
                try:
                    # Crea directory backup se non esiste
                    try:
                        ftp.mkd(backup_path)
                    except:
                        pass  # Directory già esistente
                    
                    # Copia file nel backup
                    backup_file = f"{backup_path}/{filename}"
                    ftp.rename(remote_path, backup_file)
                    self.logger.info(f"💾 Backup creato: {backup_file}")
                    
                    # Aggiorna database - USA CURSOR PASSATO COME PARAMETRO
                    cursor.execute('''
                        UPDATE synced_files 
                        SET deleted_from_server = 1, backup_created = 1
                        WHERE filename = ?
                    ''', (filename,))
                    # NON FARE COMMIT qui - sarà fatto nel metodo principale
                    
                except Exception as e:
                    self.logger.error(f"❌ Errore backup {filename}: {e}")
                    return False
            else:
                # Cancella direttamente
                ftp.delete(remote_path)
                
                # Aggiorna database - USA CURSOR PASSATO COME PARAMETRO
                cursor.execute('''
                    UPDATE synced_files 
                    SET deleted_from_server = 1
                    WHERE filename = ?
                ''', (filename,))
                # NON FARE COMMIT qui - sarà fatto nel metodo principale
            
            self.logger.info(f"🗑️  Cancellato: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Errore cancellazione {filename}: {e}")
            return False

    # === SEZIONE ELABORAZIONE FILE ===
 
    def load_json_results(self) -> bool:
        """Carica file JSON risultati nel database con backup automatico e gestione competizioni sequenziale

        Returns:
            bool: True se sono stati processati nuovi file, False altrimenti
        """
        try:
            print("\n📂 CARICAMENTO FILE JSON RISULTATI")
            
            # Backup automatico del database prima del caricamento
            print("\n💾 Creazione backup database...")
            backup_path = self.backup_database()
            if not backup_path:
                print("⚠️  Backup fallito, continuare comunque? (s/N): ", end="")
                confirm = input().strip().lower()
                if confirm not in ['s', 'si', 'sì', 'y', 'yes']:
                    print("❌ Operazione annullata")
                    return False
            
            results_path = Path(self.config['paths']['local_results'])
            if not results_path.exists():
                print(f"❌ Cartella risultati non trovata: {results_path}")
                return False
            
            json_files = list(results_path.glob('*.json'))
            if not json_files:
                print("ℹ️  Nessun file JSON trovato")
                return False
            
            print(f"\n📊 Trovati {len(json_files)} file JSON da processare")
            
            # Connessione database per controlli
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Filtra file già processati
            files_to_process = []
            for json_file in json_files:
                filename = json_file.name
                
                # Controlla se già processato in synced_files
                cursor.execute('''
                    SELECT processed_in_db, processing_result 
                    FROM synced_files 
                    WHERE filename = ? AND processed_in_db = 1
                ''', (filename,))
                
                already_processed = cursor.fetchone()
                if already_processed:
                    self.logger.debug(f"⏭️  {filename} già processato: {already_processed[1]}")
                    continue
                
                files_to_process.append(json_file)
            
            if not files_to_process:
                print("ℹ️  Tutti i file sono già stati processati")
                conn.close()
                return False
            
            print(f"\n📊 File da processare: {len(files_to_process)} (saltati: {len(json_files) - len(files_to_process)})")
            
            # MODIFICA PRINCIPALE: Ordina i file in ordine ascendente per nome (data/ora)
            files_to_process.sort(key=lambda f: f.name)
            print(f"📋 File ordinati cronologicamente per elaborazione sequenziale")
            print(f"\n🚀 INIZIO ELABORAZIONE FILE...")
            
            # Processa i file con le assegnazioni determinate
            processed = 0
            skipped = 0
            errors = 0
            empty_sessions = 0
            
            for i, json_file in enumerate(files_to_process, 1):
                filename = json_file.name
                # MESSAGGIO PER OGNI FILE:
                print(f"\n📄 [{i}/{len(files_to_process)}] {filename}")
                
                result = self.process_session_file(json_file)
                if result == 'processed':
                    processed += 1
                    print(f"  ✅ Processato con successo")
                elif result == 'processed_empty':
                    processed += 1
                    empty_sessions += 1
                    print(f"  ✅ Processato (sessione vuota)")
                elif result == 'skipped':
                    skipped += 1
                    print(f"  ⏭️  Saltato (già processato)")
                else:
                    errors += 1
                    print(f"  ❌ Errore durante elaborazione")
            
            print(f"\n✅ ELABORAZIONE COMPLETATA")
            print(f"📥 File processati: {processed}")
            if empty_sessions > 0:
                print(f"📋 Sessioni vuote: {empty_sessions}")
            print(f"⏭️  File saltati: {skipped}")
            print(f"❌ Errori: {errors}")

            # Ritorna True se sono stati processati nuovi file
            return processed > 0
            
        except Exception as e:
            self.logger.error(f"❌ Errore caricamento risultati: {e}")
            return False

    def extract_session_type_from_filename(self, filename: str) -> str:
        """Estrae il tipo di sessione dal nome file - MODIFICATO"""
        try:
            # Estrae la parte tra l'ultimo underscore e l'estensione
            # Es: 241205_143022_FP.json -> FP
            base_name = filename.replace('.json', '')
            session_type = base_name.split('_')[-1]
            
            # Verifica che sia un tipo valido - MODIFICATO: accetta anche senza numero
            if re.match(r'^(FP[1-9]?|Q[1-9]?|R[1-9]?)$', session_type):
                return session_type
            else:
                self.logger.warning(f"⚠️ Tipo sessione non riconosciuto nel filename {filename}: {session_type}")
                return session_type  # Ritorna comunque il valore estratto
                
        except Exception as e:
            self.logger.error(f"❌ Errore estrazione session_type da {filename}: {e}")
            return "UNKNOWN"

    def normalize_session_type(self, json_session_type: str, filename_session_type: str) -> str:
        """Normalizza il tipo di sessione combinando JSON e filename - MODIFICATO"""
        try:
            # Se il filename termina con _FP, _Q o _R (senza numero), mantieni così
            if filename_session_type in ['FP', 'Q', 'R']:
                return filename_session_type
            
            # Se il JSON contiene già il numero (es: "FP2"), usalo
            if re.match(r'^(FP[1-9]|Q[1-9]|R[1-9])$', json_session_type):
                return json_session_type
            
            # Se il JSON è generico (es: "FP") ma il filename è specifico (es: "FP2"), 
            # usa quello del filename
            if re.match(r'^(FP[1-9]|Q[1-9]|R[1-9])$', filename_session_type):
                return filename_session_type
            
            # Se il JSON è generico e il filename anche, MODIFICATO: non aggiungere "1"
            if json_session_type in ['FP', 'Q', 'R']:
                return json_session_type
            
            # Fallback: usa il valore del JSON
            return json_session_type
            
        except Exception as e:
            self.logger.error(f"❌ Errore normalizzazione session_type: {e}")
            return json_session_type or "UNKNOWN"
 
    def parse_filename_to_datetime(self, filename: str) -> datetime:
        """Converte nome file ACC in datetime"""
        try:
            # Pattern: AAMMDD_HHMMSS_X.json
            date_part = filename[:6]
            time_part = filename[7:13]
            
            year = 2000 + int(date_part[:2])
            month = int(date_part[2:4])
            day = int(date_part[4:6])
            hour = int(time_part[:2])
            minute = int(time_part[2:4])
            second = int(time_part[4:6])
            
            return datetime(year, month, day, hour, minute, second)
        except Exception as e:
            self.logger.error(f"❌ Errore parsing filename {filename}: {e}")
            return datetime.now()

    def process_session_file(self, filepath: Path) -> str:
        """Processa un singolo file di sessione"""
        try:
            filename = filepath.name
            
            # Controlla se già processato in sessions (per compatibilità)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT session_id FROM sessions WHERE filename = ?', (filename,))
            if cursor.fetchone():
                # Marca come processato in synced_files se non già fatto
                cursor.execute('''
                    INSERT OR IGNORE INTO synced_files (filename, file_hash, file_size, processed_in_db, processed_at, processing_result)
                    VALUES (?, 'legacy', 0, 1, ?, 'legacy_session')
                ''', (filename, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                cursor.execute('''
                    UPDATE synced_files 
                    SET processed_in_db = 1, processed_at = ?, processing_result = 'legacy_session'
                    WHERE filename = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), filename))
                conn.commit()
                conn.close()
                self.logger.debug(f"⏭️  {filename} già processato")
                return 'skipped'
            
            # Carica file JSON con gestione encoding
            try:
                with open(filepath, 'rb') as f:
                    raw_data = f.read()
                
                # Rileva encoding
                if b'\x00' in raw_data[:100] and raw_data.count(b'\x00') > len(raw_data) // 3:
                    try:
                        if raw_data.startswith(b'\xff\xfe'):
                            content = raw_data[2:].decode('utf-16-le')
                        else:
                            content = raw_data.decode('utf-16-le')
                    except:
                        try:
                            if raw_data.startswith(b'\xfe\xff'):
                                content = raw_data[2:].decode('utf-16-be')
                            else:
                                content = raw_data.decode('utf-16-be')
                        except:
                            clean_data = raw_data.replace(b'\x00', b'')
                            content = clean_data.decode('utf-8', errors='ignore')
                else:
                    content = raw_data.decode('utf-8', errors='ignore')
                
                if content.startswith('\ufeff'):
                    content = content[1:]
                
                data = json.loads(content)
                
            except Exception as e:
                self.logger.error(f"❌ Errore lettura {filename}: {e}")
                # NON marcare come processato i file con errori per permettere riprocessamento
                # self.mark_file_as_processed(cursor, filename, 'error', f"read_error: {str(e)}")
                conn.close()
                return 'error'
            
            session_id = filename.replace('.json', '')
            session_date = self.parse_filename_to_datetime(filename)
            
            # Gestione corretta del session_type
            json_session_type = data.get('sessionType', 'UNKNOWN')
            filename_session_type = self.extract_session_type_from_filename(filename)
            normalized_session_type = self.normalize_session_type(json_session_type, filename_session_type)
            
            # Gestione automatica competition_id dal serverName
            competition_id = None
            server_name = data.get('serverName', '')
            
            # Cerca pattern "id=xxx" nel serverName
            import re
            match = re.search(r'id=(\d+)', server_name)
            if match:
                extracted_comp_id = int(match.group(1))
                self.logger.info(f"📋 {filename}: Competition ID estratto dal serverName: {extracted_comp_id}")
                
                # Verifica che la competizione esiste e non è completata
                cursor.execute('SELECT is_completed FROM competitions WHERE competition_id = ?', (extracted_comp_id,))
                comp_result = cursor.fetchone()
                
                if comp_result and comp_result[0] == 0:  # Competizione esiste e non è completata
                    # Verifica che non esiste già una sessione con stesso competition_id e session_type
                    cursor.execute('''SELECT COUNT(*) FROM sessions 
                                     WHERE competition_id = ? AND session_type = ?''', 
                                  (extracted_comp_id, normalized_session_type))
                    session_count = cursor.fetchone()[0]
                    
                    if session_count == 0:  # Non esiste ancora una sessione con questi parametri
                        competition_id = extracted_comp_id
                        self.logger.info(f"📋 {filename}: Competition ID {competition_id} validato e assegnato")
                    else:
                        self.logger.warning(f"📋 {filename}: Sessione {normalized_session_type} già esistente per competition_id {extracted_comp_id}")
                else:
                    if comp_result:
                        self.logger.warning(f"📋 {filename}: Competition {extracted_comp_id} già completata")
                    else:
                        self.logger.warning(f"📋 {filename}: Competition {extracted_comp_id} non trovata nel DB")
            else:
                self.logger.info(f"📋 {filename}: Nessun competition_id trovato nel serverName")
            
            # Ottieni session_order dal JSON (sessionIndex + 1)
            session_index = data.get('sessionIndex', 0)
            session_order = session_index + 1
            
            self.logger.info(f"📋 {filename}: SessionType='{normalized_session_type}', CompID={competition_id}, Order={session_order}")
            
            # Controlla se sessione vuota
            total_laps = len(data.get('laps', []))
            
            if total_laps == 0:
                print(f"   📋 Sessione vuota rilevata - Solo aggiornamento piloti")
                
                # Aggiorna solo piloti
                for entry in data['sessionResult']['leaderBoardLines']:
                    driver_id = self.get_driver_id_from_leaderboard(entry)
                    driver_name = entry['currentDriver']['lastName']
                    short_name = entry['currentDriver'].get('shortName', '')
                    race_number = entry['car']['raceNumber']
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO drivers 
                        (driver_id, last_name, short_name, preferred_race_number, 
                         first_seen, last_seen, total_sessions, bad_driver_reports, trust_level)
                        VALUES (?, ?, ?, ?,
                               COALESCE((SELECT first_seen FROM drivers WHERE driver_id = ?), ?),
                               ?,
                               COALESCE((SELECT total_sessions FROM drivers WHERE driver_id = ?), 0),
                               COALESCE((SELECT bad_driver_reports FROM drivers WHERE driver_id = ?), 0),
                               COALESCE((SELECT trust_level FROM drivers WHERE driver_id = ?), 0))
                    ''', (driver_id, driver_name, short_name, race_number, 
                          driver_id, session_date.isoformat(), session_date.isoformat(), 
                          driver_id, driver_id, driver_id))
                
                self.mark_file_as_processed(cursor, filename, 'processed', 
                                           f'empty_session_{normalized_session_type}_drivers_only')
                
                conn.commit()
                conn.close()
                self.logger.info(f"📝 {filename} - Sessione vuota processata")
                return 'processed_empty'
            
            # Inserisci sessione
            # Determina se competition_id è stato assegnato automaticamente
            is_autoassign_comp = 1 if competition_id is not None else 0
            
            cursor.execute('''
                INSERT INTO sessions 
                (session_id, filename, session_type, track_name, server_name, 
                 session_date, best_lap_overall, total_drivers, competition_id, session_order, 
                 is_autoassign_comp, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, filename, normalized_session_type, data['trackName'],
                data.get('serverName', ''), session_date.isoformat(),
                data['sessionResult'].get('bestlap'), 
                len(data['sessionResult']['leaderBoardLines']),
                competition_id, session_order, is_autoassign_comp, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            # Processa piloti e risultati
            driver_car_mapping = {}
            position = 1
            
            for entry in data['sessionResult']['leaderBoardLines']:
                driver_id = self.get_driver_id_from_leaderboard(entry)
                driver_name = entry['currentDriver']['lastName']
                short_name = entry['currentDriver'].get('shortName', '')
                car_id = entry['car']['carId']
                race_number = entry['car']['raceNumber']
                
                driver_car_mapping[driver_id] = car_id
                
                # Inserisci/aggiorna pilota
                cursor.execute('''
                    INSERT OR REPLACE INTO drivers 
                    (driver_id, last_name, short_name, preferred_race_number, 
                     first_seen, last_seen, total_sessions, bad_driver_reports, trust_level)
                    VALUES (?, ?, ?, ?,
                           COALESCE((SELECT first_seen FROM drivers WHERE driver_id = ?), ?),
                           ?,
                           COALESCE((SELECT total_sessions FROM drivers WHERE driver_id = ?), 0) + 1,
                           COALESCE((SELECT bad_driver_reports FROM drivers WHERE driver_id = ?), 0),
                           COALESCE((SELECT trust_level FROM drivers WHERE driver_id = ?), 0))
                ''', (driver_id, driver_name, short_name, race_number, 
                      driver_id, session_date.isoformat(), session_date.isoformat(), 
                      driver_id, driver_id, driver_id))
                
                # Inserisci risultato
                timing = entry.get('timing', {})
                cursor.execute('''
                    INSERT INTO session_results 
                    (session_id, driver_id, position, car_id, race_number, car_model, 
                     best_lap, total_time, lap_count, is_spectator)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id, driver_id, position, car_id, race_number,
                    entry['car']['carModel'], timing.get('bestLap'),
                    timing.get('totalTime'), timing.get('lapCount', 0),
                    entry.get('bIsSpectator', False)
                ))
                
                position += 1
            
            # Processa giri
            lap_number = 1
            for lap in data.get('laps', []):
                car_id = lap['carId']
                driver_id = None
                for did, cid in driver_car_mapping.items():
                    if cid == car_id:
                        driver_id = did
                        break
                
                if driver_id:
                    splits = lap.get('splits', [])
                    cursor.execute('''
                        INSERT INTO laps 
                        (session_id, driver_id, car_id, lap_time, is_valid_for_best,
                         split1, split2, split3, lap_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, driver_id, car_id, lap['laptime'],
                        lap.get('isValidForBest', False),
                        splits[0] if len(splits) > 0 else None,
                        splits[1] if len(splits) > 1 else None,
                        splits[2] if len(splits) > 2 else None,
                        lap_number
                    ))
                lap_number += 1
            
            # Processa penalità
            for penalty in data.get('penalties', []):
                car_id = penalty['carId']
                driver_id = None
                for did, cid in driver_car_mapping.items():
                    if cid == car_id:
                        driver_id = did
                        break
                
                if driver_id:
                    cursor.execute('''
                        INSERT INTO penalties 
                        (session_id, driver_id, car_id, reason, penalty_type,
                         penalty_value, violation_lap, cleared_lap, is_post_race)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, driver_id, car_id, penalty['reason'],
                        penalty['penalty'], penalty.get('penaltyValue', 0),
                        penalty.get('violationInLap', 0), penalty.get('clearedInLap', 0),
                        False
                    ))
            
            # Penalità post-gara
            for penalty in data.get('post_race_penalties', []):
                car_id = penalty['carId']
                driver_id = None
                for did, cid in driver_car_mapping.items():
                    if cid == car_id:
                        driver_id = did
                        break
                
                if driver_id:
                    cursor.execute('''
                        INSERT INTO penalties 
                        (session_id, driver_id, car_id, reason, penalty_type,
                         penalty_value, violation_lap, cleared_lap, is_post_race)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, driver_id, car_id, penalty['reason'],
                        penalty['penalty'], penalty.get('penaltyValue', 0),
                        penalty.get('violationInLap', 0), penalty.get('clearedInLap', 0),
                        True
                    ))
            
            # MARCA COME PROCESSATO
            self.mark_file_as_processed(cursor, filename, 'processed', 
                                       f'full_session_{normalized_session_type}_{len(data["sessionResult"]["leaderBoardLines"])}drivers_{total_laps}laps_comp{competition_id}')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"✅ {filename} - {normalized_session_type} - {len(data['sessionResult']['leaderBoardLines'])} piloti, {total_laps} giri - CompID: {competition_id}")
            return 'processed'
            
        except Exception as e:
            self.logger.error(f"❌ Errore processando {filepath}: {e}")
            # NON marcare come processato i file con errori per permettere riprocessamento
            # try:
            #     conn = sqlite3.connect(self.db_path)
            #     cursor = conn.cursor()
            #     self.mark_file_as_processed(cursor, filepath.name, 'error', f"processing_error: {str(e)}")
            #     conn.commit()
            #     conn.close()
            # except:
            #     pass
            return 'error'
    
    def mark_file_as_processed(self, cursor, filename: str, result: str, details: str):
        """Marca un file come processato in synced_files"""
        try:
            # Prova a fare update prima
            cursor.execute('''
                UPDATE synced_files 
                SET processed_in_db = 1, processed_at = ?, processing_result = ?
                WHERE filename = ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"{result}: {details}", filename))
            
            # Se non ha aggiornato nessuna riga, inserisci nuovo record
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO synced_files 
                    (filename, file_hash, file_size, processed_in_db, processed_at, processing_result)
                    VALUES (?, 'local_file', 0, 1, ?, ?)
                ''', (filename, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"{result}: {details}"))
                
        except Exception as e:
            self.logger.error(f"❌ Errore marcatura file {filename}: {e}")

    def get_driver_id_from_leaderboard(self, leaderboard_entry: dict) -> str:
        """Estrae driver ID dal leaderboard entry"""
        try:
            return leaderboard_entry['currentDriver']['playerId']
        except KeyError:
            return leaderboard_entry['car']['drivers'][0]['playerId']
    
    def sync_and_load(self):
        """Sincronizza da G-Portal, carica nel database, sincronizza su GitHub e calcola classifiche"""
        print("\n🔄 SYNC + LOAD + GITHUB + CLASSIFICHE")

        # Prima sincronizza - PASSA auto_mode=True
        self.sync_gportal(auto_mode=True)

        # Poi carica
        print("\n📂 Caricamento file scaricati...")
        files_processed = self.load_json_results()

        # Sincronizza su GitHub solo se sono stati processati nuovi file
        if files_processed:
            print("\n📤 Sincronizzazione su GitHub...")
            github_success = self.sync_database_to_github()

            if github_success:
                print("\n✅ PROCESSO COMPLETO: Sync + Load + GitHub completato con successo")
            else:
                print("\n⚠️  PROCESSO PARZIALMENTE COMPLETATO: Sync + Load OK, GitHub fallito")
        else:
            print("\n✅ SYNC + LOAD COMPLETATO: Nessun nuovo file da elaborare, GitHub sync saltato")

    # === MENU PRINCIPALE ===
    
    def show_menu(self):
        """Mostra menu principale - VERSIONE AGGIORNATA CON AUTO MODE"""
        while True:
            print(f"\n{'='*60}")
            print(f"🏁 ACC SERVER MANAGER - {self.config['community']['name']}")
            print(f"{'='*60}")
            print("\n📋 MENU PRINCIPALE:\n")
            print("  1. Sync G-Portal (solo download)")
            print("  2. Carica file JSON risultati")
            print("  3. Sincronizza DB GitHub")
            print("  4. Sync + Load + GitHub")
            print("  5. 🤖 MODALITÀ AUTOMATICA")  # NUOVO
            print("")
            print("  0. Esci")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                self.sync_gportal()
            elif choice == "2":
                self.load_json_results()
            elif choice == "3":
                self.sync_database_to_github()
            elif choice == "4":
                self.sync_and_load()
            elif choice == "5":  # NUOVO
                self.show_auto_mode_menu()
            elif choice == "0":
                print("\n👋 Arrivederci!")
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0" and choice != "5":  # Non mostrare "premi invio" per auto mode
                input("\n↩️  Premi INVIO per continuare...")

    def show_auto_mode_menu(self):
        """Menu modalità automatica - NUOVO METODO"""
        while True:
            print(f"\n{'='*50}")
            print(f"🤖 MODALITÀ AUTOMATICA")
            print(f"{'='*50}")
            print(f"\n📋 CONFIGURAZIONE ATTUALE:")
            print(f"  ⏰ Intervallo: {self.auto_mode.interval_seconds // 60} minuti")
            print(f"  🔄 Funzione: Sync + Load + GitHub")
            print(f"  📊 Stato: {'🟢 ATTIVO' if self.auto_mode.is_running else '🔴 FERMO'}")
            
            print(f"\n📋 OPZIONI:")
            print("  1. Avvia modalità automatica")
            print("  2. Ferma modalità automatica")
            print("  3. Cambia intervallo")
            print("  0. Torna al menu principale")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                if not self.auto_mode.is_running:
                    self.auto_mode.start_auto_mode()
                    # RIMUOVI questa riga che causava il blocco:
                    # # Quando torna qui, l'auto mode è stato fermato
                else:
                    print("⚠️ Modalità automatica già attiva")
                input("\n↩️  Premi INVIO per continuare...")
            
            elif choice == "2":
                if self.auto_mode.is_running:
                    self.auto_mode.stop_auto_mode()
                    print("✅ Modalità automatica fermata")
                else:
                    print("ℹ️ Modalità automatica non è attiva")
                input("\n↩️  Premi INVIO per continuare...")
            
            elif choice == "3":
                self.change_auto_interval()
            
            elif choice == "0":
                # Se auto mode è attivo, avvisa prima di uscire
                if self.auto_mode.is_running:
                    confirm = input("\n⚠️ Modalità automatica è attiva. Fermarla? (s/N): ").strip().lower()
                    if confirm in ['s', 'si', 'sì', 'y', 'yes']:
                        self.auto_mode.stop_auto_mode()
                break
            else:
                print("❌ Scelta non valida")
                input("\n↩️  Premi INVIO per continuare...")
    
    def change_auto_interval(self):
        """Cambia intervallo modalità automatica - NUOVO METODO"""
        print(f"\n⏰ CAMBIO INTERVALLO")
        print(f"Intervallo attuale: {self.auto_mode.interval_seconds // 60} minuti")
        
        try:
            new_minutes = int(input("\nNuovo intervallo (minuti): ").strip())
            
            if new_minutes < 1:
                print("❌ L'intervallo deve essere almeno 1 minuto")
                return
            
            if new_minutes > 1440:  # 24 ore
                print("❌ L'intervallo massimo è 1440 minuti (24 ore)")
                return
            
            old_minutes = self.auto_mode.interval_seconds // 60
            self.auto_mode.interval_seconds = new_minutes * 60
            
            print(f"✅ Intervallo cambiato da {old_minutes} a {new_minutes} minuti")
            
            if self.auto_mode.is_running:
                print("ℹ️ Il nuovo intervallo sarà applicato dalla prossima esecuzione")
            
        except ValueError:
            print("❌ Inserisci un numero valido")
        
        input("\n↩️  Premi INVIO per continuare...")

def main():
    """Funzione principale"""
    try:
        print("🏁 ACC Server Manager - Gestione e Sincronizzazione")
        print("Inizializzazione...\n")
        
        manager = ACCServerManager()
        manager.show_menu()
        
    except KeyboardInterrupt:
        print("\n\n⛔ Operazione interrotta dall'utente")
    except Exception as e:
        print(f"\n❌ Errore critico: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()