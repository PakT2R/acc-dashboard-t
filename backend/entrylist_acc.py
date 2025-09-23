#!/usr/bin/env python3
"""
ACC Entrylist Manager - Gestione autonoma entrylist
Strumento per import/export e merge di entrylist per ACC
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class EntrylistManager:
    """Gestione autonoma entrylist per ACC"""
    
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
        
        log_file = log_dir / f"entrylist_manager_{datetime.now().strftime('%Y%m%d')}.log"
        
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
            print(f"📋 GESTIONE ENTRYLIST ACC")
            print(f"{'='*50}")
            print("\n📋 OPZIONI:")
            print("  1. Import entrylist")
            print("  2. Export entrylist")
            print("  3. Merge entrylist SimGrid")
            print("  0. Esci")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                self.import_entrylist()
            elif choice == "2":
                self.export_entrylist()
            elif choice == "3":
                self.merge_simgrid_entrylist()
            elif choice == "0":
                print("\n👋 Arrivederci!")
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")
    
    def import_entrylist(self):
        """Importa piloti da file entrylist"""
        try:
            print("\n📥 IMPORT ENTRYLIST")
            
            entrylist_dir = Path(self.config['paths']['import_export_entrylist'])
            entrylist_dir.mkdir(parents=True, exist_ok=True)
            
            # Lista file disponibili
            json_files = list(entrylist_dir.glob('*.json'))
            if not json_files:
                print(f"❌ Nessun file entrylist trovato in: {entrylist_dir}")
                return
            
            print("\n📁 FILE DISPONIBILI:")
            for i, file in enumerate(json_files, 1):
                print(f"  {i}. {file.name}")
            
            try:
                choice = int(input(f"\nScegli file (1-{len(json_files)}): ").strip()) - 1
                if not 0 <= choice < len(json_files):
                    print("❌ Scelta non valida")
                    return
            except ValueError:
                print("❌ Input non valido")
                return
            
            selected_file = json_files[choice]
            
            # Carica file
            with open(selected_file, 'r', encoding='utf-8') as f:
                entrylist_data = json.load(f)
            
            if 'entries' not in entrylist_data:
                print("❌ Formato entrylist non valido")
                return
            
            print(f"\n📊 Trovate {len(entrylist_data['entries'])} entries")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Contatori e liste per tracking
            imported = 0
            updated = 0
            skipped = 0
            
            imported_drivers = []
            updated_drivers = []
            skipped_drivers = []
            
            for entry in entrylist_data['entries']:
                if 'drivers' not in entry or not entry['drivers']:
                    skipped += 1
                    skipped_drivers.append({
                        'reason': 'Nessun driver nell\'entry',
                        'entry': str(entry)[:100] + '...' if len(str(entry)) > 100 else str(entry)
                    })
                    continue
                
                driver_data = entry['drivers'][0]
                player_id = driver_data.get('playerID', '').strip()
                
                if not player_id:
                    skipped += 1
                    skipped_drivers.append({
                        'reason': 'PlayerID mancante',
                        'name': f"{driver_data.get('firstName', '')} {driver_data.get('lastName', '')}".strip() or 'N/A'
                    })
                    continue
                
                # Controlla se esiste
                cursor.execute('SELECT * FROM drivers WHERE driver_id = ?', (player_id,))
                existing = cursor.fetchone()
                
                last_name = driver_data.get('lastName', '').strip() or f"Driver_{player_id[:8]}"
                first_name = driver_data.get('firstName', '').strip()
                short_name = driver_data.get('shortName', '').strip() or None
                race_number = entry.get('raceNumber') if entry.get('raceNumber', 0) > 0 else None
                
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = f"Driver_{player_id[:8]}"
                
                if existing:
                    # Aggiorna solo campi mancanti
                    updates = []
                    params = []
                    update_details = []
                    
                    if not existing[2] and short_name:  # short_name
                        updates.append('short_name = ?')
                        params.append(short_name)
                        update_details.append(f"short_name: '{short_name}'")
                    
                    if not existing[3] and race_number:  # preferred_race_number
                        updates.append('preferred_race_number = ?')
                        params.append(race_number)
                        update_details.append(f"race_number: {race_number}")
                    
                    if updates:
                        params.append(player_id)
                        cursor.execute(f'''
                            UPDATE drivers 
                            SET {', '.join(updates)}
                            WHERE driver_id = ?
                        ''', params)
                        updated += 1
                        updated_drivers.append({
                            'player_id': player_id,
                            'name': full_name,
                            'updates': update_details
                        })
                    else:
                        skipped += 1
                        skipped_drivers.append({
                            'reason': 'Nessun campo da aggiornare',
                            'player_id': player_id,
                            'name': full_name
                        })
                else:
                    # Inserisci nuovo
                    cursor.execute('''
                        INSERT INTO drivers 
                        (driver_id, last_name, short_name, preferred_race_number,
                         first_seen, last_seen, total_sessions, bad_driver_reports, trust_level)
                        VALUES (?, ?, ?, ?, NULL, NULL, 0, 0, 0)
                    ''', (player_id, last_name, short_name, race_number))
                    imported += 1
                    imported_drivers.append({
                        'player_id': player_id,
                        'name': full_name,
                        'short_name': short_name,
                        'race_number': race_number
                    })
            
            conn.commit()
            conn.close()
            
            # Mostra risultati dettagliati
            print(f"\n✅ IMPORT COMPLETATO")
            print(f"➕ Nuovi piloti: {imported}")
            print(f"🔄 Piloti aggiornati: {updated}")
            print(f"⏭️  Saltati: {skipped}")
            
            # Dettagli piloti importati
            if imported_drivers:
                print(f"\n➕ PILOTI IMPORTATI ({len(imported_drivers)}):")
                for driver in imported_drivers:
                    details = []
                    if driver['short_name']:
                        details.append(f"short: {driver['short_name']}")
                    if driver['race_number']:
                        details.append(f"#: {driver['race_number']}")
                    
                    detail_str = f" ({', '.join(details)})" if details else ""
                    print(f"  • {driver['player_id'][:8]}... - {driver['name']}{detail_str}")
            
            # Dettagli piloti aggiornati
            if updated_drivers:
                print(f"\n🔄 PILOTI AGGIORNATI ({len(updated_drivers)}):")
                for driver in updated_drivers:
                    updates_str = ', '.join(driver['updates'])
                    print(f"  • {driver['player_id'][:8]}... - {driver['name']} → {updates_str}")
            
            # Dettagli piloti saltati
            if skipped_drivers:
                print(f"\n⏭️  PILOTI SALTATI ({len(skipped_drivers)}):")
                for i, driver in enumerate(skipped_drivers, 1):
                    if 'player_id' in driver:
                        print(f"  {i}. {driver['player_id'][:8]}... - {driver['name']} → {driver['reason']}")
                    else:
                        print(f"  {i}. {driver.get('name', 'N/A')} → {driver['reason']}")
                    
                    # Limita output se troppi saltati
                    if i >= 10 and len(skipped_drivers) > 10:
                        remaining = len(skipped_drivers) - 10
                        print(f"  ... e altri {remaining} piloti saltati")
                        break
            
        except Exception as e:
            self.logger.error(f"❌ Errore import entrylist: {e}")
            print(f"❌ Errore durante import: {e}")
    
    def export_entrylist(self):
        """Esporta entrylist con filtri"""
        try:
            print("\n📤 EXPORT ENTRYLIST")
            
            print("\n📋 CRITERI DI SELEZIONE:")
            print("I piloti verranno estratti se soddisfano ALMENO UNO dei seguenti criteri:")
            print("  • Hanno un numero minimo di sessioni (anche senza trust)")
            print("  • Hanno un trust level minimo (anche senza sessioni)")
            print("  • I criteri sono in OR, non in AND")
            
            # Input parametri
            min_sessions = int(input("\nMinimo sessioni [0]: ").strip() or "0")
            
            print("\nTrust level minimo:")
            print("  0 = Tutti")
            print("  1 = Affidabili")
            print("  2 = Molto affidabili")
            min_trust = int(input("Scelta [0]: ").strip() or "0")
            
            add_bad_prefix = input("\nAggiungere prefisso BAD> ai piloti problematici? (s/N): ").strip().lower()
            add_bad_prefix = add_bad_prefix in ['s', 'si', 'sì', 'y', 'yes']
            
            # Query piloti con logica OR
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT driver_id, last_name, short_name, preferred_race_number,
                       total_sessions, bad_driver_reports, trust_level
                FROM drivers
                WHERE total_sessions >= ? OR trust_level >= ?
                ORDER BY total_sessions DESC, last_name ASC
            ''', (min_sessions, min_trust))
            
            drivers = cursor.fetchall()
            conn.close()
            
            if not drivers:
                print("❌ Nessun pilota trovato con i criteri specificati")
                return
            
            # Mostra statistiche criteri
            session_criteria = sum(1 for d in drivers if d[4] >= min_sessions)  # total_sessions
            trust_criteria = sum(1 for d in drivers if d[6] >= min_trust)       # trust_level
            both_criteria = sum(1 for d in drivers if d[4] >= min_sessions and d[6] >= min_trust)
            
            print(f"\n📊 Piloti trovati: {len(drivers)}")
            print(f"  • Con minimo {min_sessions} sessioni: {session_criteria}")
            print(f"  • Con trust level ≥ {min_trust}: {trust_criteria}")
            print(f"  • Con entrambi i criteri: {both_criteria}")
            
            # Crea entrylist
            entrylist = {
                "entries": [],
                "configVersion": 1,
                "forceEntryList": 0
            }
            
            max_bad_reports = self.config['bad_driver']['max_reports_for_warning']
            bad_prefix = self.config['bad_driver']['prefix_in_entrylist']
            
            for driver_id, last_name, short_name, race_num, sessions, bad_reports, trust in drivers:
                
                # Aggiungi prefisso se necessario
                display_name = last_name
                if add_bad_prefix and bad_reports > max_bad_reports:
                    display_name = f"{bad_prefix}{last_name}"
                
                entry = {
                    "drivers": [{
                        "firstName": "",
                        "lastName": display_name,
                        "shortName": short_name or "",
                        "playerID": driver_id,
                        "driverCategory": 2
                    }],
                    "raceNumber": -1,
                    "customCar": "",
                    "forcedCarModel": -1,
                    "overrideDriverInfo": 0,
                    "isServerAdmin": 0,
                    "overrideCarModelForCustomCar": 0,
                    "configVersion": 1
                }
                
                entrylist["entries"].append(entry)
            
            # Salva file
            output_dir = Path(self.config['paths']['import_export_entrylist'])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"entrylist_{timestamp}.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(entrylist, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ ENTRYLIST ESPORTATA")
            print(f"📁 File: {output_file}")
            print(f"👥 Piloti inclusi: {len(entrylist['entries'])}")
            print(f"📋 Criteri usati: Sessioni ≥ {min_sessions} OR Trust ≥ {min_trust}")
            
            # Mostra anteprima
            print("\n📋 ANTEPRIMA (primi 10):")
            for i, entry in enumerate(entrylist['entries'][:10]):
                driver = entry['drivers'][0]
                # Trova dati originali per mostrare criteri soddisfatti
                driver_data = next((d for d in drivers if d[0] == driver['playerID']), None)
                if driver_data:
                    sessions, trust = driver_data[4], driver_data[6]
                    criteria = []
                    if sessions >= min_sessions:
                        criteria.append(f"{sessions}s")
                    if trust >= min_trust:
                        criteria.append(f"T{trust}")
                    criteria_str = f" [{'/'.join(criteria)}]" if criteria else ""
                    print(f"  #{entry['raceNumber']:3d} - {driver['lastName']}{criteria_str}")
                else:
                    print(f"  #{entry['raceNumber']:3d} - {driver['lastName']}")
            
            if len(entrylist['entries']) > 10:
                print(f"  ... e altri {len(entrylist['entries']) - 10} piloti")
            
        except Exception as e:
            self.logger.error(f"❌ Errore export entrylist: {e}")
            print(f"❌ Errore durante export: {e}")

    def merge_simgrid_entrylist(self):
        """Merge entrylist standard con SimGrid entrylist"""
        try:
            print("\n🔄 MERGE ENTRYLIST SIMGRID")
            
            entrylist_dir = Path(self.config['paths']['import_export_entrylist'])
            
            # File paths
            standard_file = entrylist_dir / "entrylist.json"
            simgrid_file = entrylist_dir / "simgrid_entrylist.json"
            
            # Verifica esistenza file
            if not standard_file.exists():
                print(f"❌ File entrylist.json non trovato in: {entrylist_dir}")
                return
            
            if not simgrid_file.exists():
                print(f"❌ File simgrid_entrylist.json non trovato in: {entrylist_dir}")
                return
            
            # Carica file con gestione encoding multiplo
            print("📂 Caricamento file...")
            standard_data = self._load_json_with_encoding(standard_file)
            if not standard_data:
                print("❌ Impossibile leggere entrylist.json")
                return
                
            simgrid_data = self._load_json_with_encoding(simgrid_file)
            if not simgrid_data:
                print("❌ Impossibile leggere simgrid_entrylist.json")
                return
            
            # Valida struttura
            if 'entries' not in standard_data or 'entries' not in simgrid_data:
                print("❌ Formato entrylist non valido")
                return
            
            print(f"📊 Entrylist standard: {len(standard_data['entries'])} entries")
            print(f"📊 Entrylist SimGrid: {len(simgrid_data['entries'])} entries (prima pulizia)")
            
            # Pulisci duplicati amministratori SimGrid
            cleaned_simgrid_entries = self._clean_simgrid_admin_duplicates(simgrid_data['entries'])
            print(f"📊 Entrylist SimGrid: {len(cleaned_simgrid_entries)} entries (dopo pulizia)")
            
            # Ottieni prefisso bad driver
            bad_prefix = self.config['bad_driver']['prefix_in_entrylist']
            
            # Processa merge
            merged_entries = self._process_entrylist_merge(
                standard_data['entries'], 
                cleaned_simgrid_entries, 
                bad_prefix
            )
            
            # Crea entrylist merged
            merged_entrylist = {
                "entries": merged_entries,
                "configVersion": 1,
                "forceEntryList": simgrid_data.get('forceEntryList', 0)  # Usa setting SimGrid
            }
            
            # Salva file merged
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = entrylist_dir / f"entrylist_merged_{timestamp}.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged_entrylist, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ MERGE COMPLETATO")
            print(f"📁 File creato: {output_file}")
            print(f"👥 Entries totali: {len(merged_entries)}")
            
            # Mostra statistiche merge
            self._show_merge_statistics(standard_data['entries'], cleaned_simgrid_entries, merged_entries, bad_prefix)
            
        except Exception as e:
            self.logger.error(f"❌ Errore merge entrylist: {e}")
            print(f"❌ Errore durante merge: {e}")

    def _load_json_with_encoding(self, filepath: Path) -> dict:
        """Carica file JSON con gestione encoding multiplo"""
        try:
            # Leggi file come bytes per rilevare encoding
            with open(filepath, 'rb') as f:
                raw_data = f.read()
            
            print(f"📄 Caricamento {filepath.name}...")
            
            # Rileva e gestisci encoding
            if raw_data.startswith(b'\xff\xfe'):
                # UTF-16 LE con BOM
                print(f"  📝 Rilevato UTF-16 LE con BOM")
                content = raw_data[2:].decode('utf-16-le')
            elif raw_data.startswith(b'\xfe\xff'):
                # UTF-16 BE con BOM
                print(f"  📝 Rilevato UTF-16 BE con BOM")
                content = raw_data[2:].decode('utf-16-be')
            elif raw_data.startswith(b'\xef\xbb\xbf'):
                # UTF-8 con BOM
                print(f"  📝 Rilevato UTF-8 con BOM")
                content = raw_data[3:].decode('utf-8')
            elif b'\x00' in raw_data[:100] and raw_data.count(b'\x00') > len(raw_data) // 3:
                # Probabilmente UTF-16 senza BOM
                try:
                    print(f"  📝 Tentativo UTF-16 LE senza BOM")
                    content = raw_data.decode('utf-16-le')
                except:
                    try:
                        print(f"  📝 Tentativo UTF-16 BE senza BOM")
                        content = raw_data.decode('utf-16-be')
                    except:
                        print(f"  📝 Fallback UTF-8 con rimozione null bytes")
                        clean_data = raw_data.replace(b'\x00', b'')
                        content = clean_data.decode('utf-8', errors='ignore')
            else:
                # UTF-8 standard
                print(f"  📝 Rilevato UTF-8 standard")
                content = raw_data.decode('utf-8', errors='ignore')
            
            # Rimuovi BOM se presente nel contenuto
            if content.startswith('\ufeff'):
                content = content[1:]
            
            # Parse JSON
            data = json.loads(content)
            print(f"  ✅ File caricato correttamente")
            return data
            
        except Exception as e:
            print(f"  ❌ Errore caricamento {filepath.name}: {e}")
            self.logger.error(f"❌ Errore caricamento {filepath}: {e}")
            return None

    def _clean_simgrid_admin_duplicates(self, simgrid_entries: list) -> list:
        """Rimuove duplicati amministratori SimGrid (entries vuote quando esiste versione completa)"""
        print("\n🧹 Pulizia duplicati amministratori SimGrid...")
        
        # Raggruppa entries per player_id
        entries_by_id = {}
        
        for entry in simgrid_entries:
            if not entry.get('drivers') or not entry['drivers']:
                continue
                
            driver = entry['drivers'][0]
            player_id = driver.get('playerID', '').strip()
            
            if not player_id:
                continue
            
            if player_id not in entries_by_id:
                entries_by_id[player_id] = []
            
            entries_by_id[player_id].append(entry)
        
        # Pulisci duplicati per ogni player_id
        cleaned_entries = []
        
        for player_id, entries in entries_by_id.items():
            if len(entries) == 1:
                # Nessun duplicato
                cleaned_entries.append(entries[0])
            else:
                # Duplicati: scegli il migliore
                print(f"  🔍 Player {player_id}: {len(entries)} entries, selezionando la migliore...")
                
                # Ordina per completezza dati (nome non vuoto, isServerAdmin=0)
                def entry_score(entry):
                    driver = entry['drivers'][0]
                    score = 0
                    
                    # Preferisci nomi non vuoti
                    if driver.get('lastName', '').strip():
                        score += 10
                    if driver.get('firstName', '').strip():
                        score += 5
                    if driver.get('shortName', '').strip():
                        score += 3
                    
                    # Preferisci non admin (isServerAdmin=0)
                    if not entry.get('isServerAdmin', 0):
                        score += 20
                    
                    # Preferisci raceNumber valido
                    if entry.get('raceNumber', -1) > 0:
                        score += 2
                    
                    return score
                
                # Seleziona entry con score più alto
                best_entry = max(entries, key=entry_score)
                cleaned_entries.append(best_entry)
                
                # Debug info
                driver = best_entry['drivers'][0]
                admin_status = "admin" if best_entry.get('isServerAdmin', 0) else "player"
                print(f"    ✅ Scelto: {driver.get('lastName', 'N/A')} ({admin_status})")
        
        print(f"  📊 Entries originali: {len(simgrid_entries)}")
        print(f"  📊 Entries pulite: {len(cleaned_entries)}")
        print(f"  🗑️  Rimossi: {len(simgrid_entries) - len(cleaned_entries)} duplicati")
        
        return cleaned_entries

    def _process_entrylist_merge(self, standard_entries: list, simgrid_entries: list, bad_prefix: str) -> list:
        """Processa il merge delle entrylist"""
        merged_entries = []
        used_player_ids = set()
        
        # Dizionari per lookup rapido
        standard_by_id = {}
        simgrid_by_id = {}
        
        # Indicizza entrylist standard
        for entry in standard_entries:
            if 'drivers' in entry and entry['drivers']:
                player_id = entry['drivers'][0].get('playerID', '').strip()
                if player_id:
                    standard_by_id[player_id] = entry
        
        # Indicizza entrylist SimGrid
        for entry in simgrid_entries:
            if 'drivers' in entry and entry['drivers']:
                driver = entry['drivers'][0]
                player_id = driver.get('playerID', '').strip()
                if player_id:
                    simgrid_by_id[player_id] = entry
        
        # FASE 1: Processa entries SimGrid (priorità alta)
        print("\n🔄 Fase 1: Processamento entries SimGrid...")
        
        for player_id, simgrid_entry in simgrid_by_id.items():
            if player_id in used_player_ids:
                continue
            
            # Controlla se esiste anche in standard
            if player_id in standard_by_id:
                standard_entry = standard_by_id[player_id]
                standard_driver = standard_entry['drivers'][0]
                standard_name = standard_driver.get('lastName', '').strip()
                
                # Se il nome standard ha prefisso BAD, usa i dati standard CON raceNumber = -1
                if standard_name.startswith(bad_prefix):
                    print(f"  ⚠️  {player_id}: Usando dati standard (BAD driver) - {standard_name}")
                    merged_entry = self._normalize_entry_format(standard_entry, 'standard')
                    # Forza raceNumber = -1 per BAD drivers
                    merged_entry['raceNumber'] = -1
                else:
                    print(f"  🔄 {player_id}: Usando dati SimGrid (priorità) - {simgrid_entry['drivers'][0].get('lastName', 'N/A')}")
                    merged_entry = self._normalize_entry_format(simgrid_entry, 'simgrid')
                    # Mantieni il raceNumber originale da SimGrid
            else:
                print(f"  ➕ {player_id}: Nuovo da SimGrid - {simgrid_entry['drivers'][0].get('lastName', 'N/A')}")
                merged_entry = self._normalize_entry_format(simgrid_entry, 'simgrid')
                # Mantieni il raceNumber originale da SimGrid
            
            used_player_ids.add(player_id)
            merged_entries.append(merged_entry)
        
        # FASE 2: Aggiungi entries solo da standard (che non sono stati processati)
        print("\n🔄 Fase 2: Processamento entries solo standard...")
        
        for player_id, standard_entry in standard_by_id.items():
            if player_id not in used_player_ids:
                print(f"  ➕ {player_id}: Solo in standard - {standard_entry['drivers'][0].get('lastName', 'N/A')}")
                merged_entry = self._normalize_entry_format(standard_entry, 'standard')
                # raceNumber = -1 per entries solo da standard (già gestito in _normalize_entry_format)
                
                used_player_ids.add(player_id)
                merged_entries.append(merged_entry)
        
        return merged_entries

    def _normalize_entry_format(self, entry: dict, source: str) -> dict:
        """Normalizza il formato dell'entry per compatibilità"""
        driver = entry['drivers'][0] if entry.get('drivers') else {}
        
        # LOGICA MODIFICATA: Imposta numero di gara in base alla fonte
        if source == 'simgrid':
            # Mantieni il numero di gara originale da SimGrid
            race_number = entry.get('raceNumber', 0)
            print(f"    🔢 Numero gara SimGrid mantenuto: {race_number}")
        else:
            # Imposta sempre -1 per entrylist standard
            race_number = -1
            print(f"    🔢 Numero gara standard impostato: -1")
        
        # Formato standard ACC
        normalized = {
            "drivers": [{
                "firstName": driver.get('firstName', ''),
                "lastName": driver.get('lastName', ''),
                "shortName": driver.get('shortName', ''),
                "playerID": driver.get('playerID', ''),
                "driverCategory": driver.get('driverCategory', 2)
            }],
            "raceNumber": race_number,  # Ora gestito correttamente
            "customCar": entry.get('customCar', ''),
            "forcedCarModel": entry.get('forcedCarModel', -1),
            "overrideDriverInfo": entry.get('overrideDriverInfo', 0),
            "isServerAdmin": entry.get('isServerAdmin', 0),
            "overrideCarModelForCustomCar": entry.get('overrideCarModelForCustomCar', 0),
            "configVersion": 1
        }
        
        return normalized

    def _show_merge_statistics(self, standard_entries: list, simgrid_entries: list, merged_entries: list, bad_prefix: str):
        """Mostra statistiche dettagliate del merge"""
        print(f"\n📊 STATISTICHE MERGE:")
        print(f"  📋 Standard entries: {len(standard_entries)}")
        print(f"  📋 SimGrid entries: {len(simgrid_entries)}")
        print(f"  📋 Merged entries: {len(merged_entries)}")
        
        # Analizza composizione merge
        standard_only = 0
        simgrid_only = 0
        both_sources = 0
        bad_drivers = 0
        
        # Indicizza per analisi
        standard_ids = set()
        simgrid_ids = set()
        
        for entry in standard_entries:
            if 'drivers' in entry and entry['drivers']:
                player_id = entry['drivers'][0].get('playerID', '').strip()
                if player_id:
                    standard_ids.add(player_id)
        
        for entry in simgrid_entries:
            if 'drivers' in entry and entry['drivers']:
                player_id = entry['drivers'][0].get('playerID', '').strip()
                if player_id:
                    simgrid_ids.add(player_id)
        
        # Analizza merged entries
        for entry in merged_entries:
            if 'drivers' in entry and entry['drivers']:
                driver = entry['drivers'][0]
                player_id = driver.get('playerID', '').strip()
                last_name = driver.get('lastName', '').strip()
                
                if player_id:
                    if player_id in standard_ids and player_id in simgrid_ids:
                        both_sources += 1
                    elif player_id in standard_ids:
                        standard_only += 1
                    elif player_id in simgrid_ids:
                        simgrid_only += 1
                    
                    if last_name.startswith(bad_prefix):
                        bad_drivers += 1
        
        print(f"\n📈 COMPOSIZIONE MERGE:")
        print(f"  🔄 Da entrambe le fonti: {both_sources}")
        print(f"  📋 Solo da standard: {standard_only}")
        print(f"  🎮 Solo da SimGrid: {simgrid_only}")
        print(f"  ⚠️  Bad drivers: {bad_drivers}")
        
        # Verifica coerenza
        total_calculated = both_sources + standard_only + simgrid_only
        if total_calculated == len(merged_entries):
            print(f"  ✅ Verifica coerenza: OK")
        else:
            print(f"  ❌ Verifica coerenza: ERRORE ({total_calculated} vs {len(merged_entries)})")


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
        manager = EntrylistManager()
        
        # Mostra menu
        manager.show_menu()
        
    except Exception as e:
        print(f"❌ Errore durante l'inizializzazione: {e}")
        return


if __name__ == "__main__":
    main()