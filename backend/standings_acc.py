#!/usr/bin/env python3
"""
ACC SERVER MANAGER - Championship and Standings System
Standalone version with championship management capabilities
"""

import sqlite3
import json
import csv
from datetime import datetime
from pathlib import Path
import logging

class ChampionshipManager:
    """Gestione classifiche e campionati per ACC Server Manager"""
    
    def __init__(self, config_file='acc_config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.db_path = self.config['database']['path']
        self.logger = self._setup_logger()  # Ora può essere chiamato
        
        # Verifica esistenza database
        if not Path(self.db_path).exists():
            print(f"❌ Database non trovato: {self.db_path}")
            print("Esegui prima il manager principale per creare il database")
            exit(1)
    
    def load_config(self) -> dict:
        """Carica configurazione da file"""
        if not Path(self.config_file).exists():
            print(f"⚠️  File config non trovato: {Path.cwd() / self.config_file}")
            exit(1)
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Errore caricamento configurazione: {e}")
            exit(1)
    
    def _setup_logger(self):
        """Setup logger"""
        logger = logging.getLogger('ChampionshipManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def show_menu(self):
        """Menu principale gestione campionati"""
        while True:
            print(f"\n{'='*60}")
            print(f"🏆 GESTIONE CAMPIONATI E CLASSIFICHE")
            print(f"{'='*60}")
            print("\n📋 CALCOLO E VISUALIZZAZIONE:")
            print("  1. Calcola classifica campionato")
            print("  2. Calcola classifica competizione")
            print("  3. Mostra classifica campionato")
            print("  4. Mostra classifica competizione")
            print("\n🔧 CONFIGURAZIONE:")
            print("  5. Gestione sistemi punti")
            print("  6. Assegna sistema punti a competizione")
            print("  7. Gestione penalità manuali")
            print("\n⚙️ STRUMENTI:")
            print("  8. Strumenti avanzati")
            print("  0. Esci")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "2":
                self._calculate_competition_results_interactive()
            elif choice == "1":
                self._calculate_championship_standings_interactive()
            elif choice == "3":
                self.show_championship_standings()
            elif choice == "4":
                self.show_competition_results()
            elif choice == "5":
                self.manage_points_systems()
            elif choice == "6":
                self.assign_points_system_to_competition()
            elif choice == "7":
                self.manage_manual_penalties()
            elif choice == "8":
                self.championships_advanced_menu()
            elif choice == "0":
                print("\n👋 Arrivederci!")
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")

    # === CALCOLO RISULTATI COMPETIZIONI ===

    def calculate_competition_results(self, competition_id: int):
        """Calcola i risultati di una competizione basandosi sulle sessioni - VERSIONE CORRETTA"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🏁 Calcolo risultati competizione {competition_id}...")
            
            # Ottieni informazioni competizione
            cursor.execute('''
                SELECT c.name, c.points_system_json, c.track_name,
                       ps.position_points_json, ps.pole_position_points, ps.fastest_lap_points,
                       ps.minimum_classified_percentage, ps.points_for_unclassified
                FROM competitions c
                LEFT JOIN points_systems ps ON c.points_system_json = ps.name
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            comp_info = cursor.fetchone()
            if not comp_info:
                print(f"❌ Competizione {competition_id} non trovata")
                return
            
            comp_name, points_system_ref, track, pos_points_json, pole_pts, fast_pts, min_classified, pts_unclassified = comp_info
            
            # Configurazione sistema punti
            if pos_points_json:
                position_points = json.loads(pos_points_json)
            elif points_system_ref:
                try:
                    position_points = json.loads(points_system_ref)
                    pole_pts = pole_pts or 1
                    fast_pts = fast_pts or 1
                except:
                    print(f"⚠️ Sistema punti non valido, uso sistema standard")
                    position_points = {"1": 25, "2": 18, "3": 15, "4": 12, "5": 10, "6": 8, "7": 6, "8": 4, "9": 2, "10": 1}
                    pole_pts = 1
                    fast_pts = 1
            else:
                print(f"⚠️ Nessun sistema punti definito, uso sistema standard")
                position_points = {"1": 25, "2": 18, "3": 15, "4": 12, "5": 10, "6": 8, "7": 6, "8": 4, "9": 2, "10": 1}
                pole_pts = 1
                fast_pts = 1
            
            print(f"📋 Competizione: {comp_name} ({track})")
            print(f"🎯 Sistema punti: {position_points}")
            print(f"🥇 Punti pole: {pole_pts} | ⚡ Punti giro veloce: {fast_pts}")
            
            # Trova sessioni
            cursor.execute('''
                SELECT session_id, session_type, filename
                FROM sessions 
                WHERE competition_id = ?
                ORDER BY session_order, session_date
            ''', (competition_id,))
            
            sessions = cursor.fetchall()
            if not sessions:
                print(f"❌ Nessuna sessione trovata per competizione {competition_id}")
                return
            
            print(f"📋 Sessioni trovate: {len(sessions)}")
            
            # STEP 1: Cancella risultati precedenti
            print(f"🧹 Cancellazione risultati precedenti...")
            cursor.execute('DELETE FROM competition_session_results WHERE competition_id = ?', (competition_id,))
            cursor.execute('DELETE FROM competition_results WHERE competition_id = ?', (competition_id,))
            
            # STEP 2: Calcola risultati per ogni sessione
            print(f"🔄 Calcolo risultati per sessione...")
            
            for session_id, session_type, filename in sessions:
                print(f"  📋 Processando sessione {session_type} ({session_id})")
                
                # Ottieni risultati sessione
                cursor.execute('''
                    SELECT sr.driver_id, sr.position, sr.lap_count, sr.best_lap, d.last_name
                    FROM session_results sr
                    JOIN drivers d ON sr.driver_id = d.driver_id
                    WHERE sr.session_id = ? AND sr.is_spectator = FALSE
                    ORDER BY sr.position ASC NULLS LAST
                ''', (session_id,))
                
                session_results = cursor.fetchall()
                
                if not session_results:
                    print(f"    ⚠️ Nessun risultato per sessione {session_type}")
                    continue
                
                # Calcola punti giro veloce per questa sessione
                fastest_lap_driver = None
                if fast_pts > 0:
                    cursor.execute('''
                        SELECT sr.driver_id, sr.best_lap
                        FROM session_results sr
                        WHERE sr.session_id = ? AND sr.is_spectator = FALSE AND sr.best_lap IS NOT NULL
                        ORDER BY sr.best_lap ASC
                        LIMIT 1
                    ''', (session_id,))
                    
                    fastest_result = cursor.fetchone()
                    if fastest_result:
                        fastest_lap_driver = fastest_result[0]
                
                # Salva risultati per ogni pilota in questa sessione
                for driver_id, position, lap_count, best_lap, driver_name in session_results:
                    # Calcola punti per questa sessione
                    session_points = 0
                    is_classified = position is not None
                    
                    # Punti per posizione (solo se classificato in gara)
                    if position is not None and session_type.startswith('R'):
                        pos_str = str(position)
                        if pos_str in position_points:
                            session_points = position_points[pos_str]
                    
                    # Punti pole position (solo per sessioni Q)
                    if position == 1 and session_type.startswith('Q') and pole_pts > 0:
                        session_points += pole_pts
                    
                    # NOTA: I punti fastest lap NON vengono aggiunti qui ma calcolati
                    # separatamente durante l'aggregazione in competition_results
                    
                    # Salva in competition_session_results
                    cursor.execute('''
                        INSERT OR REPLACE INTO competition_session_results
                        (competition_id, driver_id, session_id, session_type, position, 
                         points, best_lap_time, total_laps, is_classified, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        competition_id, driver_id, session_id, session_type, position,
                        session_points, best_lap, lap_count or 0, is_classified,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                
                print(f"    ✅ {len(session_results)} piloti processati")
            
            # STEP 3: Aggrega risultati in competition_results
            print(f"📊 Aggregazione risultati finali...")
            
            # Ottieni tutti i piloti che hanno partecipato
            cursor.execute('''
                SELECT DISTINCT driver_id 
                FROM competition_session_results 
                WHERE competition_id = ?
            ''', (competition_id,))
            
            drivers = [row[0] for row in cursor.fetchall()]
            
            for driver_id in drivers:
                # Calcola punti gara (solo posizioni, dalle sessioni R)
                cursor.execute('''
                    SELECT SUM(points)
                    FROM competition_session_results
                    WHERE competition_id = ? AND driver_id = ? AND session_type LIKE 'R%'
                ''', (competition_id, driver_id))
                
                race_points = cursor.fetchone()[0] or 0
                
                # Calcola punti pole (dalle sessioni Q)
                cursor.execute('''
                    SELECT SUM(points)
                    FROM competition_session_results
                    WHERE competition_id = ? AND driver_id = ? AND session_type LIKE 'Q%'
                ''', (competition_id, driver_id))
                
                pole_points = cursor.fetchone()[0] or 0
                
                # Calcola punti fastest lap (conta i fastest lap ottenuti solo nelle sessioni R)
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM competition_session_results csr
                    JOIN (
                        SELECT session_id, MIN(best_lap_time) as fastest_lap
                        FROM competition_session_results
                        WHERE competition_id = ? AND best_lap_time IS NOT NULL AND session_type LIKE 'R%'
                        GROUP BY session_id
                    ) fl ON csr.session_id = fl.session_id AND csr.best_lap_time = fl.fastest_lap
                    WHERE csr.competition_id = ? AND csr.driver_id = ?
                ''', (competition_id, competition_id, driver_id))
                
                fastest_laps_count = cursor.fetchone()[0] or 0
                fastest_lap_points = fastest_laps_count * fast_pts
                
                # Calcola totale finale
                total_points = race_points + pole_points + fastest_lap_points
                
                # Salva in competition_results
                cursor.execute('''
                    INSERT OR REPLACE INTO competition_results
                    (competition_id, driver_id, race_points, pole_points, fastest_lap_points, 
                     bonus_points, penalty_points, total_points, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    competition_id, driver_id, race_points, pole_points, fastest_lap_points,
                    0, 0, total_points, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            
            # STEP 4: Mostra riepilogo
            print(f"\n📊 Riepilogo finale:")
            cursor.execute('''
                SELECT d.last_name, cr.race_points, cr.pole_points, cr.fastest_lap_points, cr.total_points
                FROM competition_results cr
                JOIN drivers d ON cr.driver_id = d.driver_id
                WHERE cr.competition_id = ?
                ORDER BY cr.total_points DESC, cr.race_points DESC
            ''', (competition_id,))
            
            final_results = cursor.fetchall()
            for driver_name, race_pts, pole_pts, fast_pts, total_pts in final_results:
                print(f"  ✅ {driver_name}: {total_pts} punti ({race_pts}+{pole_pts}+{fast_pts})")
            
            conn.commit()
            conn.close()
            
            print(f"✅ Risultati competizione {competition_id} calcolati e salvati")
            print(f"📋 Salvati {len(drivers)} piloti in {len(sessions)} sessioni")
            
        except Exception as e:
            self.logger.error(f"❌ Errore calcolo risultati competizione: {e}")
            import traceback
            traceback.print_exc()

    def calculate_championship_standings(self, championship_id: int):
        """Calcola la classifica di un campionato - VERSIONE CORRETTA"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🏆 Calcolo classifica campionato {championship_id}...")
            
            # Ottieni informazioni campionato
            cursor.execute('''
                SELECT name, season, description 
                FROM championships 
                WHERE championship_id = ?
            ''', (championship_id,))
            
            champ_info = cursor.fetchone()
            if not champ_info:
                print(f"❌ Campionato {championship_id} non trovato")
                return
            
            champ_name, season, description = champ_info
            print(f"🏆 Campionato: {champ_name} ({season})")
            
            # Ottieni competizioni del campionato (completate O con sessioni auto-assegnate)
            cursor.execute('''
                SELECT DISTINCT c.competition_id, c.name, c.track_name, ps.drop_worst_results
                FROM competitions c
                LEFT JOIN points_systems ps ON c.points_system_json = ps.name
                LEFT JOIN sessions s ON c.competition_id = s.competition_id
                WHERE c.championship_id = ? 
                AND (c.is_completed = TRUE OR s.is_autoassign_comp = 1)
                ORDER BY c.round_number
            ''', (championship_id,))
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print(f"❌ Nessuna competizione completata o con sessioni auto-assegnate trovata")
                return
            
            print(f"🏁 Competizioni incluse nel calcolo: {len(competitions)}")
            
            # Determina regola drop_worst_results
            drop_worst = competitions[0][3] if competitions[0][3] else 0
            
            # Raccoglie risultati per pilota
            driver_results = {}
            
            for comp_id, comp_name, track, _ in competitions:
                # CORREZIONE: Per ogni competizione, trova chi ha fatto il giro veloce
                # dai risultati delle sessioni, non dai punti assegnati
                cursor.execute('''
                    SELECT driver_id
                    FROM competition_session_results
                    WHERE competition_id = ? AND best_lap_time IS NOT NULL AND session_type LIKE 'R%'
                    ORDER BY best_lap_time ASC
                    LIMIT 1
                ''', (comp_id,))
                
                fastest_lap_result = cursor.fetchone()
                fastest_lap_driver_id = fastest_lap_result[0] if fastest_lap_result else None
                
                # Recupera tutti i risultati della competizione - AGGIORNATO
                cursor.execute('''
                    SELECT cr.driver_id, cr.total_points, d.last_name
                    FROM competition_results cr
                    JOIN drivers d ON cr.driver_id = d.driver_id
                    WHERE cr.competition_id = ? AND cr.total_points > 0
                    ORDER BY cr.total_points DESC
                ''', (comp_id,))
                
                comp_results = cursor.fetchall()
                
                for driver_id, points, driver_name in comp_results:
                    if driver_id not in driver_results:
                        driver_results[driver_id] = {
                            'driver_name': driver_name,
                            'competition_results': [],
                            'total_points': 0,
                            'competitions_participated': 0,
                            'wins': 0,
                            'podiums': 0,
                            'poles': 0,
                            'fastest_laps': 0,
                            'best_position': None,
                            'positions': []
                        }
                    
                    # Aggiungi risultato
                    driver_results[driver_id]['competition_results'].append({
                        'competition_id': comp_id,
                        'points': points
                    })
                    
                    driver_results[driver_id]['competitions_participated'] += 1
                    
                    # Calcola posizione finale nella competizione basandosi sui punti
                    # (La posizione nella competizione è determinata dall'ordine nei punti)
                    current_position = len([r for r in comp_results if r[1] > points]) + 1
                    driver_results[driver_id]['positions'].append(current_position)
                    
                    # Conta vittorie nelle sessioni R (posizione 1)
                    cursor.execute('''
                        SELECT COUNT(*)
                        FROM competition_session_results
                        WHERE competition_id = ? AND driver_id = ? AND session_type LIKE 'R%' AND position = 1
                    ''', (comp_id, driver_id))
                    
                    race_wins = cursor.fetchone()[0]
                    driver_results[driver_id]['wins'] += race_wins
                    
                    # Conta podi nelle sessioni R (posizione 1-3)
                    cursor.execute('''
                        SELECT COUNT(*)
                        FROM competition_session_results
                        WHERE competition_id = ? AND driver_id = ? AND session_type LIKE 'R%' AND position <= 3
                    ''', (comp_id, driver_id))
                    
                    race_podiums = cursor.fetchone()[0]
                    driver_results[driver_id]['podiums'] += race_podiums
                    
                    # Conta pole positions dalle sessioni di qualifica
                    cursor.execute('''
                        SELECT COUNT(*)
                        FROM competition_session_results
                        WHERE competition_id = ? AND driver_id = ? AND session_type LIKE 'Q%' AND position = 1
                    ''', (comp_id, driver_id))
                    
                    poles_count = cursor.fetchone()[0]
                    driver_results[driver_id]['poles'] += poles_count
                    
                    # Conta fastest laps nelle sessioni R (chi ha fatto il tempo migliore per sessione)
                    cursor.execute('''
                        SELECT COUNT(*)
                        FROM competition_session_results csr
                        JOIN (
                            SELECT session_id, MIN(best_lap_time) as fastest_lap
                            FROM competition_session_results
                            WHERE competition_id = ? AND session_type LIKE 'R%' AND best_lap_time IS NOT NULL
                            GROUP BY session_id
                        ) fl ON csr.session_id = fl.session_id AND csr.best_lap_time = fl.fastest_lap
                        WHERE csr.competition_id = ? AND csr.driver_id = ?
                    ''', (comp_id, comp_id, driver_id))
                    
                    fastest_laps_count = cursor.fetchone()[0]
                    driver_results[driver_id]['fastest_laps'] += fastest_laps_count
                    
                    # Migliore posizione
                    if (driver_results[driver_id]['best_position'] is None or 
                        current_position < driver_results[driver_id]['best_position']):
                        driver_results[driver_id]['best_position'] = current_position
            
            # Calcola punti finali con drop worst results
            for driver_id, data in driver_results.items():
                all_points = [result['points'] for result in data['competition_results']]
                
                if drop_worst > 0 and len(all_points) > drop_worst:
                    sorted_points = sorted(all_points, reverse=True)
                    points_to_count = sorted_points[:-drop_worst]
                    points_dropped = sum(sorted_points[-drop_worst:])
                    data['total_points'] = sum(points_to_count)
                    data['points_dropped'] = points_dropped
                else:
                    data['total_points'] = sum(all_points)
                    data['points_dropped'] = 0
                
                # Statistiche aggiuntive
                if data['positions']:
                    data['average_position'] = sum(data['positions']) / len(data['positions'])
                    
                    # Consistency rating
                    if len(data['positions']) > 1:
                        pos_variance = sum((pos - data['average_position']) ** 2 for pos in data['positions']) / len(data['positions'])
                        consistency = max(0, 100 - (pos_variance * 5))
                        data['consistency_rating'] = round(consistency, 1)
                    else:
                        data['consistency_rating'] = 100.0
                else:
                    data['average_position'] = None
                    data['consistency_rating'] = 0.0
            
            # Ottieni penalità manuali
            cursor.execute('''
                SELECT driver_id, SUM(penalty_points) as total_penalties
                FROM manual_penalties 
                WHERE championship_id = ? AND is_active = TRUE
                GROUP BY driver_id
            ''', (championship_id,))
            
            penalties = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Applica penalità
            for driver_id, penalty_points in penalties.items():
                if driver_id in driver_results:
                    driver_results[driver_id]['total_points'] -= penalty_points
            
            # Ordina per punti
            sorted_drivers = sorted(driver_results.items(), 
                                   key=lambda x: (-x[1]['total_points'], x[1]['average_position'] or 999))
            
            # Assegna posizioni
            for i, (driver_id, data) in enumerate(sorted_drivers):
                data['position'] = i + 1
            
            # Salva classifica
            print(f"\n📊 Salvando classifica...")
            
            cursor.execute('DELETE FROM championship_standings WHERE championship_id = ?', (championship_id,))
            
            for driver_id, data in driver_results.items():
                cursor.execute('''
                    INSERT INTO championship_standings
                    (championship_id, driver_id, total_points, position,
                     competitions_participated, wins, podiums, poles, fastest_laps,
                     points_dropped, average_position, best_position, consistency_rating,
                     last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    championship_id, driver_id, data['total_points'], data['position'],
                    data['competitions_participated'], data['wins'], data['podiums'], 
                    data['poles'], data['fastest_laps'], data['points_dropped'],
                    data['average_position'], data['best_position'], data['consistency_rating'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
            
            conn.commit()
            conn.close()
            
            # Mostra classifica
            print(f"\n🏆 CLASSIFICA FINALE {champ_name}:")
            print(f"{'Pos':<4} {'Pilota':<25} {'Punti':<6}")
            print("-" * 37)

            for driver_id, data in sorted_drivers:
                print(f"{data['position']:<4} {data['driver_name']:<25} {data['total_points']:<6}")

            print(f"\n✅ Classifica campionato {championship_id} calcolata e salvata")
            print(f"💡 Usa 'Mostra classifica campionato' per vedere tutti i dettagli")
            
        except Exception as e:
            self.logger.error(f"❌ Errore calcolo classifica campionato: {e}")

    # === VISUALIZZAZIONE ===

    def show_championship_standings(self, championship_id: int = None):
        """Mostra classifica campionato"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if championship_id is None:
                # NUOVO ORDINAMENTO: prima completati (data_start), poi non completati (data_start)
                cursor.execute('''
                    SELECT ch.championship_id, ch.name, ch.season, ch.start_date, ch.is_completed,
                           COUNT(DISTINCT cs.driver_id) as drivers_in_standings
                    FROM championships ch
                    LEFT JOIN championship_standings cs ON ch.championship_id = cs.championship_id
                    GROUP BY ch.championship_id
                    ORDER BY 
                        CASE WHEN ch.is_completed = 1 THEN 0 ELSE 1 END,  -- Prima completati (0), poi non completati (1)
                        ch.start_date ASC NULLS LAST
                ''')
                
                championships = cursor.fetchall()
                
                if not championships:
                    print("❌ Nessun campionato trovato")
                    return
                
                print(f"\n🏆 CAMPIONATI DISPONIBILI:")
                for champ_id, name, season, start_date, is_completed, drivers_in_standings in championships:
                    # Icone stato
                    completion_status = "✅" if is_completed else "🔄"
                    calculation_status = "✅" if drivers_in_standings > 0 else "⏳"
                    
                    # Info stagione e data
                    season_info = f" ({season})" if season else ""
                    date_str = f" - {start_date[:10]}" if start_date else ""
                    
                    print(f"  {champ_id}. {completion_status}{calculation_status} {name}{season_info}{date_str}")
                
                print(f"\n📋 LEGENDA:")
                print(f"  Primo simbolo: ✅ Completato | 🔄 In corso")
                print(f"  Secondo simbolo: ✅ Calcolato | ⏳ Da calcolare")
                
                try:
                    championship_id = int(input(f"\nID campionato: ").strip())
                except ValueError:
                    print("❌ ID non valido")
                    return
            
            # Ottieni informazioni campionato
            cursor.execute('''
                SELECT name, season, description
                FROM championships 
                WHERE championship_id = ?
            ''', (championship_id,))
            
            champ_info = cursor.fetchone()
            if not champ_info:
                print(f"❌ Campionato {championship_id} non trovato")
                return
            
            champ_name, season, description = champ_info
            
            # Ottieni classifica            
            # QUERY MODIFICATA: include penalità manuali
            cursor.execute('''
                SELECT cs.position, d.last_name, cs.total_points, cs.competitions_participated,
                       cs.wins, cs.podiums, cs.poles, cs.fastest_laps, cs.points_dropped,
                       cs.average_position, cs.best_position, cs.consistency_rating,
                       COALESCE(mp.total_penalties, 0) as manual_penalties
                FROM championship_standings cs
                JOIN drivers d ON cs.driver_id = d.driver_id
                LEFT JOIN (
                    SELECT driver_id, SUM(penalty_points) as total_penalties
                    FROM manual_penalties 
                    WHERE championship_id = ? AND is_active = TRUE
                    GROUP BY driver_id
                ) mp ON cs.driver_id = mp.driver_id
                WHERE cs.championship_id = ?
                ORDER BY cs.position
            ''', (championship_id, championship_id))
            
            standings = cursor.fetchall()
            
            if not standings:
                print(f"❌ Nessuna classifica trovata - calcola prima la classifica")
                return
            
            # Mostra classifica
            print(f"\n{'='*90}")
            print(f"🏆 CLASSIFICA: {champ_name}")
            if season:
                print(f"📅 Stagione: {season}")
            print(f"{'='*90}")
            
            print(f"\n🏁 CLASSIFICA:")
            print(f"{'Pos':<4} {'Pilota':<25} {'Punti':<15} {'Gare':<5} {'Vitt':<4} {'Podi':<4} {'Pole':<4} {'FL':<3} {'Pen':<4}")
            print("-" * 75)

            for pos, name, points, races, wins, podiums, poles, fastest_laps, dropped, avg_pos, best_pos, consistency, penalties in standings:
                # Formatta punti con dettagli
                if dropped and dropped > 0 and penalties > 0:
                    points_str = f"{points} (-{dropped}D, -{penalties}P)"
                elif dropped and dropped > 0:
                    points_str = f"{points} (-{dropped}D)"
                elif penalties > 0:
                    points_str = f"{points} (-{penalties}P)"
                else:
                    points_str = str(points)
                
                # Mostra penalità nella colonna dedicata
                penalty_str = f"-{penalties}" if penalties > 0 else ""
                
                print(f"{pos:<4} {name:<25} {points_str:<15} {races:<5} {wins:<4} {podiums:<4} {poles:<4} {fastest_laps:<3} {penalty_str:<4}")
            
            # Mostra dettaglio penalità se presenti
            cursor.execute('''
                SELECT d.last_name, mp.penalty_points, mp.reason, mp.applied_date
                FROM manual_penalties mp
                JOIN drivers d ON mp.driver_id = d.driver_id
                WHERE mp.championship_id = ? AND mp.is_active = TRUE
                ORDER BY d.last_name, mp.applied_date
            ''', (championship_id,))
            
            penalties_detail = cursor.fetchall()
            
            if penalties_detail:
                print(f"\n⚠️ PENALITÀ MANUALI:")
                print(f"{'Pilota':<25} {'Punti':<6} {'Motivo':<30} {'Data'}")
                print("-" * 70)
                
                for driver_name, penalty_points, reason, applied_date in penalties_detail:
                    date_str = applied_date[:10] if applied_date else "N/A"
                    reason_short = reason[:28] + ".." if len(reason) > 30 else reason
                    print(f"{driver_name:<25} -{penalty_points:<5} {reason_short:<30} {date_str}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione classifica: {e}")

    def show_competition_results(self, competition_id: int = None):
        """Mostra risultati competizione"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if competition_id is None:
                # NUOVO ORDINAMENTO: prima calcolate (data_start), poi non calcolate (data_start)
                cursor.execute('''
                    SELECT c.competition_id, c.name, c.track_name, c.date_start,
                           ch.name as championship_name,
                           COUNT(cr.competition_id) as has_results
                    FROM competitions c
                    LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                    LEFT JOIN competition_results cr ON c.competition_id = cr.competition_id
                    GROUP BY c.competition_id
                    ORDER BY 
                        CASE WHEN COUNT(cr.competition_id) > 0 THEN 0 ELSE 1 END,  -- Prima calcolate (0), poi non calcolate (1)
                        c.date_start ASC NULLS LAST
                ''')
                
                competitions = cursor.fetchall()
                
                if not competitions:
                    print("❌ Nessuna competizione trovata")
                    return
                
                print(f"\n🏁 COMPETIZIONI:")
                for comp_id, comp_name, track, date_start, champ_name, has_results in competitions:
                    # Icona stato calcolo
                    calc_status = "✅" if has_results > 0 else "⏳"
                    
                    # Info campionato
                    champ_info = f" ({champ_name})" if champ_name else " (Libera)"
                    
                    # Formato data
                    date_str = f" - {date_start[:10]}" if date_start else ""
                    
                    print(f"  {comp_id}. {calc_status} {comp_name} - {track}{date_str}{champ_info}")
                
                try:
                    competition_id = int(input("\nID competizione: ").strip())
                except ValueError:
                    print("❌ ID non valido")
                    return
            
            # Ottieni informazioni competizione
            cursor.execute('''
                SELECT c.name, c.track_name, ch.name as championship_name
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            comp_info = cursor.fetchone()
            if not comp_info:
                print(f"❌ Competizione {competition_id} non trovata")
                return
            
            comp_name, track, champ_name = comp_info
            
            # Ottieni risultati - AGGIORNATO per nuova struttura
            cursor.execute('''
                SELECT d.last_name, cr.race_points, cr.pole_points, cr.fastest_lap_points, cr.total_points
                FROM competition_results cr
                JOIN drivers d ON cr.driver_id = d.driver_id
                WHERE cr.competition_id = ?
                ORDER BY cr.total_points DESC, cr.race_points DESC
            ''', (competition_id,))
            
            results = cursor.fetchall()
            
            if not results:
                print(f"❌ Nessun risultato trovato - calcola prima i risultati")
                return
            
            # Mostra risultati
            print(f"\n{'='*60}")
            print(f"🏁 RISULTATI: {comp_name}")
            print(f"📍 Pista: {track}")
            if champ_name:
                print(f"🏆 Campionato: {champ_name}")
            print(f"{'='*60}")
            
            print(f"\n{'Pos':<4} {'Pilota':<25} {'Punti':<15}")
            print("-" * 50)
            
            for position, (name, race_pts, pole_pts, fast_pts, total_pts) in enumerate(results, 1):
                points_detail = f"{race_pts}"
                if pole_pts > 0:
                    points_detail += f"+{pole_pts}(P)"
                if fast_pts > 0:
                    points_detail += f"+{fast_pts}(FL)"
                points_str = f"{total_pts} ({points_detail})"
                
                print(f"{position:<4} {name:<25} {points_str:<15}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione risultati: {e}")

    # === GESTIONE SISTEMI PUNTI ===

    def manage_points_systems(self):
        """Gestione sistemi di punteggio"""
        while True:
            print(f"\n{'='*50}")
            print(f"🎯 GESTIONE SISTEMI PUNTI")
            print(f"{'='*50}")
            
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Mostra sistemi esistenti
                cursor.execute('''
                    SELECT system_id, name, description, pole_position_points, 
                           fastest_lap_points, drop_worst_results, is_active
                    FROM points_systems 
                    ORDER BY system_id
                ''')
                
                systems = cursor.fetchall()
                
                if systems:
                    print("\n📋 SISTEMI PUNTI DISPONIBILI:")
                    for sys_id, name, desc, pole_pts, fast_pts, drop_results, is_active in systems:
                        status = "✅" if is_active else "❌"
                        drop_info = f" (Drop {drop_results})" if drop_results > 0 else ""
                        print(f"  {sys_id:2d}. {status} {name}{drop_info}")
                
                print(f"\n📋 OPZIONI:")
                print("  1. Visualizza dettagli sistema")
                print("  2. Crea nuovo sistema")
                print("  3. Modifica sistema esistente")
                print("  4. Attiva/Disattiva sistema")
                print("  0. Torna indietro")
                
                choice = input("\nScelta: ").strip()
                
                if choice == "1":
                    self._show_points_system_details(cursor)
                elif choice == "2":
                    self._create_points_system(cursor)
                    conn.commit()
                elif choice == "3":
                    self._modify_points_system(cursor)
                    conn.commit()
                elif choice == "4":
                    self._toggle_points_system(cursor)
                    conn.commit()
                elif choice == "0":
                    break
                else:
                    print("❌ Scelta non valida")
                
                conn.close()
                
                if choice != "0":
                    input("\n↩️  Premi INVIO per continuare...")
            
            except Exception as e:
                self.logger.error(f"❌ Errore gestione sistemi punti: {e}")

    def _show_points_system_details(self, cursor):
        """Mostra dettagli sistema punti"""
        try:
            system_id = int(input("\nID sistema da visualizzare: ").strip())
            
            cursor.execute('''
                SELECT name, description, position_points_json, pole_position_points,
                       fastest_lap_points, drop_worst_results
                FROM points_systems 
                WHERE system_id = ?
                ORDER BY system_id
            ''', (system_id,))
            
            system = cursor.fetchone()
            if not system:
                print(f"❌ Sistema {system_id} non trovato")
                return
            
            name, desc, points_json, pole_pts, fast_pts, drop_results = system
            
            print(f"\n🎯 SISTEMA: {name}")
            print(f"📝 Descrizione: {desc}")
            print(f"🥇 Punti pole: {pole_pts}")
            print(f"⚡ Punti giro veloce: {fast_pts}")
            print(f"📉 Drop worst: {drop_results}")
            
            print(f"\n🏁 PUNTI PER POSIZIONE:")
            try:
                position_points = json.loads(points_json)
                for pos in sorted(position_points.keys(), key=int):
                    print(f"  P{pos}: {position_points[pos]} punti")
            except:
                print(f"  ❌ Errore parsing punti")
                
        except ValueError:
            print("❌ ID non valido")
        except Exception as e:
            print(f"❌ Errore: {e}")

    def _create_points_system(self, cursor):
        """Crea nuovo sistema punti"""
        try:
            print(f"\n📝 CREAZIONE NUOVO SISTEMA PUNTI")
            
            name = input("Nome sistema: ").strip()
            if not name:
                print("❌ Nome obbligatorio")
                return
            
            description = input("Descrizione [opzionale]: ").strip()
            
            # Punti per posizioni
            print(f"\n🏁 DEFINIZIONE PUNTI PER POSIZIONE:")
            print("Inserisci i punti per ogni posizione (INVIO per terminare)")
            
            position_points = {}
            position = 1
            
            while True:
                try:
                    points_input = input(f"P{position}: ").strip()
                    if not points_input:
                        break
                    
                    points = int(points_input)
                    if points < 0:
                        print("❌ I punti non possono essere negativi")
                        continue
                    
                    position_points[str(position)] = points
                    position += 1
                    
                except ValueError:
                    print("❌ Inserisci un numero valido")
            
            if not position_points:
                print("❌ Devi definire almeno una posizione")
                return
            
            # Punti bonus
            try:
                pole_pts = int(input(f"\nPunti pole position [0]: ").strip() or "0")
                fast_pts = int(input(f"Punti giro veloce [0]: ").strip() or "0")
                drop_results = int(input(f"Drop worst results [0]: ").strip() or "0")
            except ValueError:
                print("❌ Valori non validi")
                return
            
            # Salva sistema
            points_json = json.dumps(position_points)
            
            cursor.execute('''
                INSERT INTO points_systems 
                (name, description, position_points_json, pole_position_points,
                 fastest_lap_points, drop_worst_results)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, points_json, pole_pts, fast_pts, drop_results))
            
            print(f"✅ Sistema punti '{name}' creato con successo")
            
        except Exception as e:
            self.logger.error(f"❌ Errore creazione sistema punti: {e}")

    def _modify_points_system(self, cursor):
        """Modifica sistema punti esistente"""
        try:
            system_id = int(input("\nID sistema da modificare: ").strip())
            
            cursor.execute('SELECT * FROM points_systems WHERE system_id = ?', (system_id,))
            system = cursor.fetchone()
            
            if not system:
                print(f"❌ Sistema {system_id} non trovato")
                return
            
            print(f"\n🔧 MODIFICA SISTEMA: {system[1]}")
            print("Lascia vuoto per mantenere valore attuale")
            
            # Modifica campi
            updates = []
            params = []
            
            new_name = input(f"Nome [{system[1]}]: ").strip()
            if new_name:
                updates.append('name = ?')
                params.append(new_name)
            
            new_desc = input(f"Descrizione [{system[2] or 'N/A'}]: ").strip()
            if new_desc:
                updates.append('description = ?')
                params.append(new_desc)
            
            new_pole = input(f"Punti pole [{system[4]}]: ").strip()
            if new_pole:
                try:
                    updates.append('pole_position_points = ?')
                    params.append(int(new_pole))
                except ValueError:
                    print("❌ Valore pole non valido, ignorato")
            
            new_fast = input(f"Punti giro veloce [{system[5]}]: ").strip()
            if new_fast:
                try:
                    updates.append('fastest_lap_points = ?')
                    params.append(int(new_fast))
                except ValueError:
                    print("❌ Valore giro veloce non valido, ignorato")
            
            if updates:
                params.append(system_id)
                sql = f"UPDATE points_systems SET {', '.join(updates)} WHERE system_id = ?"
                cursor.execute(sql, params)
                print(f"✅ Sistema {system_id} modificato")
            else:
                print("ℹ️ Nessuna modifica effettuata")
                
        except ValueError:
            print("❌ ID non valido")
        except Exception as e:
            self.logger.error(f"❌ Errore modifica sistema: {e}")

    def _toggle_points_system(self, cursor):
        """Attiva/disattiva sistema punti"""
        try:
            system_id = int(input("\nID sistema da attivare/disattivare: ").strip())
            
            cursor.execute('SELECT name, is_active FROM points_systems WHERE system_id = ?', (system_id,))
            system = cursor.fetchone()
            
            if not system:
                print(f"❌ Sistema {system_id} non trovato")
                return
            
            name, is_active = system
            new_status = not is_active
            
            cursor.execute('UPDATE points_systems SET is_active = ? WHERE system_id = ?', 
                          (new_status, system_id))
            
            status_text = "attivato" if new_status else "disattivato"
            print(f"✅ Sistema '{name}' {status_text}")
            
        except ValueError:
            print("❌ ID non valido")
        except Exception as e:
            self.logger.error(f"❌ Errore toggle sistema: {e}")

    def assign_points_system_to_competition(self):
        """Assegna sistema punti a una competizione"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🎯 ASSEGNAZIONE SISTEMA PUNTI")
            
            # Mostra competizioni
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.points_system_json
                FROM competitions c
                ORDER BY date_start
            ''')
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print("❌ Nessuna competizione trovata")
                return
            
            print(f"\n🏁 COMPETIZIONI:")
            for comp_id, comp_name, track, current_system in competitions:
                current_info = f" - {current_system}" if current_system else " - Nessun sistema"
                print(f"  {comp_id:2d}. {comp_name} - {track}{current_info}")
            
            try:
                comp_id = int(input(f"\nID competizione: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            # Mostra sistemi punti
            cursor.execute('''
                SELECT system_id, name, description 
                FROM points_systems 
                WHERE is_active = TRUE
                ORDER BY system_id
            ''')
            
            systems = cursor.fetchall()
            
            print(f"\n🎯 SISTEMI PUNTI:")
            print("  0. Rimuovi sistema punti")
            for sys_id, name, desc in systems:
                print(f"  {sys_id:2d}. {name}")
            
            try:
                sys_choice = int(input(f"\nScelta sistema: ").strip())
            except ValueError:
                print("❌ Scelta non valida")
                return
            
            if sys_choice == 0:
                cursor.execute('UPDATE competitions SET points_system_json = NULL WHERE competition_id = ?', 
                              (comp_id,))
                print(f"✅ Sistema punti rimosso")
            else:
                cursor.execute('SELECT name FROM points_systems WHERE system_id = ?', (sys_choice,))
                sys_result = cursor.fetchone()
                
                if not sys_result:
                    print(f"❌ Sistema non trovato")
                    return
                
                sys_name = sys_result[0]
                cursor.execute('UPDATE competitions SET points_system_json = ? WHERE competition_id = ?', 
                              (sys_name, comp_id))
                print(f"✅ Sistema '{sys_name}' assegnato")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore assegnazione sistema: {e}")

    # === GESTIONE PENALITÀ ===

    def manage_manual_penalties(self):
        """Gestione penalità manuali"""
        while True:
            print(f"\n{'='*50}")
            print(f"⚠️ GESTIONE PENALITÀ MANUALI")
            print(f"{'='*50}")
            
            print(f"\n📋 OPZIONI:")
            print("  1. Visualizza penalità esistenti")
            print("  2. Aggiungi penalità")
            print("  3. Rimuovi penalità")
            print("  0. Torna indietro")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                self._show_manual_penalties()
            elif choice == "2":
                self._add_manual_penalty()
            elif choice == "3":
                self._remove_manual_penalty()
            elif choice == "0":
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")

    def _show_manual_penalties(self):
        """Mostra penalità manuali esistenti"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT mp.penalty_id, ch.name as championship_name, d.last_name,
                       mp.penalty_points, mp.reason, mp.applied_date, mp.is_active
                FROM manual_penalties mp
                JOIN championships ch ON mp.championship_id = ch.championship_id
                JOIN drivers d ON mp.driver_id = d.driver_id
                ORDER BY mp.applied_date DESC
            ''')
            
            penalties = cursor.fetchall()
            
            if not penalties:
                print("ℹ️ Nessuna penalità trovata")
                return
            
            print(f"\n⚠️ PENALITÀ MANUALI:")
            print(f"{'ID':<3} {'Campionato':<20} {'Pilota':<20} {'Punti':<6} {'Stato':<8} {'Motivo'}")
            print("-" * 80)
            
            for penalty_id, champ_name, driver_name, points, reason, applied_date, is_active in penalties:
                status = "✅ Attiva" if is_active else "❌ Disattiva"
                print(f"{penalty_id:<3} {champ_name[:19]:<20} {driver_name[:19]:<20} {points:<6} {status:<8} {reason[:30]}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore visualizzazione penalità: {e}")

    def _add_manual_penalty(self):
        """Aggiungi penalità manuale"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n➕ AGGIUNTA PENALITÀ")
            
            # Selezione campionato
            cursor.execute('SELECT championship_id, name, season FROM championships ORDER BY season DESC, name')
            championships = cursor.fetchall()
            
            if not championships:
                print("❌ Nessun campionato trovato")
                return
            
            print(f"\n🏆 CAMPIONATI:")
            for champ_id, name, season in championships:
                season_info = f" ({season})" if season else ""
                print(f"  {champ_id}. {name}{season_info}")
            
            try:
                champ_id = int(input("\nID campionato: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            # Selezione pilota
            cursor.execute('''
                SELECT DISTINCT d.driver_id, d.last_name
                FROM drivers d
                JOIN championship_standings cs ON d.driver_id = cs.driver_id
                WHERE cs.championship_id = ?
                ORDER BY d.last_name
            ''', (champ_id,))
            
            drivers = cursor.fetchall()
            
            if not drivers:
                print("❌ Nessun pilota nel campionato")
                return
            
            print(f"\n👤 PILOTI:")
            for i, (driver_id, name) in enumerate(drivers, 1):
                print(f"  {i}. {name}")
            
            try:
                driver_choice = int(input("\nNumero pilota: ").strip()) - 1
                if not 0 <= driver_choice < len(drivers):
                    print("❌ Scelta non valida")
                    return
            except ValueError:
                print("❌ Input non valido")
                return
            
            driver_id, driver_name = drivers[driver_choice]
            
            # Dettagli penalità
            try:
                penalty_points = int(input(f"\nPunti penalità: ").strip())
            except ValueError:
                print("❌ Punti non validi")
                return
            
            reason = input("Motivo penalità: ").strip()
            if not reason:
                print("❌ Motivo obbligatorio")
                return
            
            applied_by = input("Applicata da [opzionale]: ").strip() or None
            
            # Salva penalità
            cursor.execute('''
                INSERT INTO manual_penalties
                (championship_id, driver_id, penalty_points, reason, applied_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (champ_id, driver_id, penalty_points, reason, applied_by))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Penalità di {penalty_points} punti applicata a {driver_name}")
            
            # NUOVO: Ricalcolo automatico classifica
            print(f"\n🔄 Ricalcolo automatico classifica campionato...")
            
            try:
                self.calculate_championship_standings(champ_id)
                print(f"✅ Classifica campionato ricalcolata automaticamente")
            except Exception as e:
                print(f"⚠️ Errore ricalcolo automatico: {e}")
                print(f"💡 Ricalcola manualmente la classifica del campionato")
            
        except Exception as e:
            self.logger.error(f"❌ Errore aggiunta penalità: {e}")

    def _remove_manual_penalty(self):
        """Rimuovi penalità manuale"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT mp.penalty_id, ch.name as championship_name, d.last_name,
                       mp.penalty_points, mp.reason, mp.championship_id
                FROM manual_penalties mp
                JOIN championships ch ON mp.championship_id = ch.championship_id
                JOIN drivers d ON mp.driver_id = d.driver_id
                WHERE mp.is_active = TRUE
                ORDER BY mp.applied_date DESC
            ''')
            
            penalties = cursor.fetchall()
            
            if not penalties:
                print("ℹ️ Nessuna penalità attiva")
                return
            
            print(f"\n⚠️ PENALITÀ ATTIVE:")
            for penalty_id, champ_name, driver_name, points, reason, champ_id in penalties:
                print(f"  {penalty_id}. {driver_name} ({champ_name}) - {points} punti - {reason}")
            
            try:
                penalty_id = int(input("\nID penalità da rimuovere: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            # Trova championship_id della penalità da rimuovere
            selected_penalty = next((p for p in penalties if p[0] == penalty_id), None)
            if not selected_penalty:
                print(f"❌ Penalità {penalty_id} non trovata")
                return
            
            champ_id = selected_penalty[5]  # championship_id è il 6° elemento (indice 5)
            
            # Disattiva penalità
            cursor.execute('UPDATE manual_penalties SET is_active = FALSE WHERE penalty_id = ?', (penalty_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                
                print(f"✅ Penalità {penalty_id} rimossa")
                
                # NUOVO: Ricalcolo automatico classifica
                print(f"\n🔄 Ricalcolo automatico classifica campionato...")
                
                try:
                    self.calculate_championship_standings(champ_id)
                    print(f"✅ Classifica campionato ricalcolata automaticamente")
                except Exception as e:
                    print(f"⚠️ Errore ricalcolo automatico: {e}")
                    print(f"💡 Ricalcola manualmente la classifica del campionato")
            else:
                print(f"❌ Penalità {penalty_id} non trovata")
                conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore rimozione penalità: {e}")

    # === STRUMENTI AVANZATI ===

    def championships_advanced_menu(self):
        """Menu strumenti avanzati"""
        while True:
            print(f"\n{'='*50}")
            print(f"🔧 STRUMENTI AVANZATI")
            print(f"{'='*50}")
            
            print(f"\n📋 OPZIONI:")
            print("  1. Calcolo automatico completo")
            print("  2. Esporta classifica CSV")
            print("  3. Statistiche campionati")
            print("  4. Verifica integrità dati")
            print("  0. Torna indietro")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                self.bulk_calculate_all_results()
            elif choice == "2":
                self._export_championship_csv_interactive()
            elif choice == "3":
                self.show_championship_stats_summary()
            elif choice == "4":
                self._verify_championship_data_integrity()
            elif choice == "0":
                break
            else:
                print("❌ Scelta non valida")
            
            if choice != "0":
                input("\n↩️  Premi INVIO per continuare...")

    def bulk_calculate_all_results(self):
        """Calcola automaticamente tutti i risultati"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🔄 CALCOLO AUTOMATICO COMPLETO")
            print("Calcolo tutti i risultati delle competizioni e classifiche campionati")
            
            confirm = input("\nProcedere? (s/N): ").strip().lower()
            if confirm not in ['s', 'si', 'sì', 'y', 'yes']:
                print("❌ Operazione annullata")
                return
            
            # Trova competizioni completate
            cursor.execute('''
                SELECT competition_id, name, track_name
                FROM competitions 
                WHERE is_completed = TRUE
                ORDER BY round_number
            ''')
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print("❌ Nessuna competizione completata")
                return
            
            print(f"\n🏁 Calcolo risultati per {len(competitions)} competizioni...")
            
            calculated_competitions = 0
            for comp_id, comp_name, track in competitions:
                try:
                    print(f"  📋 {comp_name} ({track})")
                    self.calculate_competition_results(comp_id)
                    calculated_competitions += 1
                except Exception as e:
                    print(f"    ❌ Errore: {e}")
            
            # Trova campionati
            cursor.execute('''
                SELECT DISTINCT ch.championship_id, ch.name, ch.season
                FROM championships ch
                JOIN competitions c ON ch.championship_id = c.championship_id
                WHERE c.is_completed = TRUE
            ''')
            
            championships = cursor.fetchall()
            
            print(f"\n🏆 Calcolo classifiche per {len(championships)} campionati...")
            
            calculated_championships = 0
            for champ_id, champ_name, season in championships:
                try:
                    season_info = f" ({season})" if season else ""
                    print(f"  🏆 {champ_name}{season_info}")
                    self.calculate_championship_standings(champ_id)
                    calculated_championships += 1
                except Exception as e:
                    print(f"    ❌ Errore: {e}")
            
            conn.close()
            
            print(f"\n✅ CALCOLO COMPLETATO")
            print(f"🏁 Competizioni: {calculated_competitions}/{len(competitions)}")
            print(f"🏆 Campionati: {calculated_championships}/{len(championships)}")
            
        except Exception as e:
            self.logger.error(f"❌ Errore calcolo automatico: {e}")

    def _export_championship_csv_interactive(self):
        """Export classifica in CSV"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT ch.championship_id, ch.name, ch.season,
                       COUNT(cs.driver_id) as drivers_count
                FROM championships ch
                JOIN championship_standings cs ON ch.championship_id = cs.championship_id
                GROUP BY ch.championship_id
                ORDER BY ch.season DESC, ch.name
            ''')
            
            championships = cursor.fetchall()
            
            if not championships:
                print("❌ Nessun campionato con classifica")
                return
            
            print(f"\n🏆 CAMPIONATI:")
            for champ_id, name, season, drivers in championships:
                season_info = f" ({season})" if season else ""
                print(f"  {champ_id}. {name}{season_info} - {drivers} piloti")
            
            try:
                champ_id = int(input("\nID campionato: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            if not any(row[0] == champ_id for row in championships):
                print(f"❌ Campionato non trovato")
                return
            
            self.export_championship_standings_csv(champ_id)
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore export CSV: {e}")

    def export_championship_standings_csv(self, championship_id: int):
        """Esporta classifica in CSV"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Ottieni info campionato
            cursor.execute('''
                SELECT name, season
                FROM championships 
                WHERE championship_id = ?
            ''', (championship_id,))
            
            champ_info = cursor.fetchone()
            if not champ_info:
                print(f"❌ Campionato non trovato")
                return
            
            champ_name, season = champ_info
            
            # Ottieni classifica
            cursor.execute('''
                SELECT cs.position, d.last_name, cs.total_points, cs.competitions_participated,
                       cs.wins, cs.podiums, cs.poles, cs.fastest_laps, cs.points_dropped
                FROM championship_standings cs
                JOIN drivers d ON cs.driver_id = d.driver_id
                WHERE cs.championship_id = ?
                ORDER BY cs.position
            ''', (championship_id,))
            
            standings = cursor.fetchall()
            
            if not standings:
                print(f"❌ Nessuna classifica trovata")
                return
            
            # Crea file CSV
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            season_info = f"_{season}" if season else ""
            safe_name = "".join(c for c in champ_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            
            output_file = f"classifica_{safe_name}{season_info}_{timestamp}.csv"
            
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header
                writer.writerow([
                    'Posizione', 'Pilota', 'Punti_Totali', 'Gare_Partecipate',
                    'Vittorie', 'Podi', 'Pole_Position', 'Giri_Veloci', 'Punti_Scartati'
                ])
                
                # Dati
                for row in standings:
                    writer.writerow(row)
            
            conn.close()
            
            print(f"✅ Classifica esportata: {output_file}")
            print(f"📊 {len(standings)} piloti esportati")
            
        except Exception as e:
            self.logger.error(f"❌ Errore export CSV: {e}")

    def show_championship_stats_summary(self):
        """Statistiche campionati"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*60}")
            print(f"📊 STATISTICHE CAMPIONATI")
            print(f"{'='*60}")
            
            # Statistiche generali
            cursor.execute('SELECT COUNT(*) FROM championships')
            total_championships = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM competitions WHERE is_completed = TRUE')
            completed_competitions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT driver_id) FROM championship_standings')
            total_drivers = cursor.fetchone()[0]
            
            print(f"\n📈 GENERALI:")
            print(f"  • Campionati: {total_championships}")
            print(f"  • Competizioni completate: {completed_competitions}")
            print(f"  • Piloti partecipanti: {total_drivers}")
            
            # Campionati più attivi
            # QUERY CORRETTA per campionati più attivi
            cursor.execute('''
                SELECT ch.name, ch.season, 
                       COUNT(DISTINCT c.competition_id) as competitions,
                       COUNT(DISTINCT cs.driver_id) as drivers
                FROM championships ch
                LEFT JOIN competitions c ON ch.championship_id = c.championship_id 
                LEFT JOIN championship_standings cs ON ch.championship_id = cs.championship_id
                WHERE c.competition_id IS NOT NULL  -- Solo campionati con competizioni
                GROUP BY ch.championship_id
                ORDER BY competitions DESC
                LIMIT 5
            ''')
            
            active_championships = cursor.fetchall()
            
            if active_championships:
                print(f"\n🏆 CAMPIONATI PIÙ ATTIVI:")
                for name, season, comps, drivers in active_championships:
                    season_info = f" ({season})" if season else ""
                    print(f"  • {name}{season_info}: {comps} competizioni, {drivers} piloti")
                
            # Piloti più vincenti
            cursor.execute('''
                SELECT d.last_name, SUM(cs.wins) as total_wins, 
                       SUM(cs.total_points) as total_points
                FROM championship_standings cs
                JOIN drivers d ON cs.driver_id = d.driver_id
                GROUP BY cs.driver_id
                HAVING total_wins > 0
                ORDER BY total_wins DESC
                LIMIT 10
            ''')
            
            top_winners = cursor.fetchall()
            
            if top_winners:
                print(f"\n🥇 PILOTI PIÙ VINCENTI:")
                for name, wins, points in top_winners:
                    print(f"  • {name}: {wins} vittorie, {points} punti totali")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore statistiche: {e}")

    def _verify_championship_data_integrity(self):
        """Verifica integrità dati"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🔍 VERIFICA INTEGRITÀ DATI")
            
            issues = []
            
            # Competizioni senza risultati
            cursor.execute('''
                SELECT c.competition_id, c.name
                FROM competitions c
                LEFT JOIN competition_results cr ON c.competition_id = cr.competition_id
                WHERE cr.competition_id IS NULL AND c.is_completed = TRUE
            ''')
            
            competitions_without_results = cursor.fetchall()
            if competitions_without_results:
                issues.append(f"Competizioni senza risultati: {len(competitions_without_results)}")
            
            # Campionati senza classifiche
            cursor.execute('''
                SELECT ch.championship_id, ch.name
                FROM championships ch
                JOIN competitions c ON ch.championship_id = c.championship_id
                LEFT JOIN championship_standings cs ON ch.championship_id = cs.championship_id
                WHERE c.is_completed = TRUE AND cs.championship_id IS NULL
                GROUP BY ch.championship_id
            ''')
            
            championships_without_standings = cursor.fetchall()
            if championships_without_standings:
                issues.append(f"Campionati senza classifiche: {len(championships_without_standings)}")
            
            # Competizioni senza sistema punti
            cursor.execute('''
                SELECT COUNT(*)
                FROM competitions
                WHERE points_system_json IS NULL AND is_completed = TRUE
            ''')
            
            competitions_without_points = cursor.fetchone()[0]
            if competitions_without_points > 0:
                issues.append(f"Competizioni senza sistema punti: {competitions_without_points}")
            
            # Mostra risultati
            if issues:
                print(f"\n⚠️ PROBLEMI RILEVATI:")
                for issue in issues:
                    print(f"  • {issue}")
                
                print(f"\n💡 SUGGERIMENTI:")
                print(f"  • Calcola risultati competizioni mancanti")
                print(f"  • Calcola classifiche campionati")
                print(f"  • Assegna sistemi punti")
            else:
                print(f"\n✅ NESSUN PROBLEMA RILEVATO")
                print(f"Tutti i dati sembrano integri")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Errore verifica integrità: {e}")

    # === INTERFACCE INTERATTIVE ===

    def _calculate_competition_results_interactive(self):
        """Interfaccia calcolo risultati competizione"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # NUOVO ORDINAMENTO: prima non calcolate (data_start), poi calcolate (data_start)
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.date_start,
                       COUNT(cr.competition_id) as has_results, c.is_completed
                FROM competitions c
                LEFT JOIN competition_results cr ON c.competition_id = cr.competition_id
                GROUP BY c.competition_id
                ORDER BY 
                    CASE WHEN COUNT(cr.competition_id) > 0 THEN 0 ELSE 1 END,  -- Prima calcolati (0), poi non calcolati (1)
                    c.date_start ASC NULLS LAST
            ''')
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print("❌ Nessuna competizione trovata")
                return
            
            print(f"\n🏁 COMPETIZIONI:")
            for comp_id, comp_name, track, date_start, has_results, is_completed in competitions:
                # Icone per stato calcolo risultati
                result_status = " ✅ Calcolati" if has_results > 0 else " ⏳ Da calcolare"
                completion_status = " (Completata)" if is_completed else " (In corso)"
                
                # Formato data
                date_str = f" - {date_start[:10]}" if date_start else ""
                
                print(f"  {comp_id}. {comp_name} - {track}{date_str}{result_status}{completion_status}")
            
            try:
                comp_id = int(input("\nID competizione: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            if not any(row[0] == comp_id for row in competitions):
                print(f"❌ Competizione non trovata")
                return
            
            conn.close()
            self.calculate_competition_results(comp_id)
            
        except Exception as e:
            self.logger.error(f"❌ Errore interfaccia calcolo risultati: {e}")

    def _calculate_championship_standings_interactive(self):
        """Interfaccia calcolo classifica campionato"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # QUERY CORRETTA: mostra tutti i campionati che hanno competizioni (calcolate o no)
            cursor.execute('''
                SELECT ch.championship_id, ch.name, ch.season, ch.start_date,
                       COUNT(DISTINCT CASE WHEN cr.competition_id IS NOT NULL THEN c.competition_id END) as calculated_competitions,
                       COUNT(DISTINCT c.competition_id) as total_competitions,
                       COUNT(DISTINCT cs.driver_id) as drivers_in_standings
                FROM championships ch
                LEFT JOIN competitions c ON ch.championship_id = c.championship_id
                LEFT JOIN competition_results cr ON c.competition_id = cr.competition_id
                LEFT JOIN championship_standings cs ON ch.championship_id = cs.championship_id
                WHERE c.competition_id IS NOT NULL  -- Solo campionati che hanno almeno una competizione
                GROUP BY ch.championship_id
                ORDER BY 
                    CASE WHEN COUNT(DISTINCT cs.driver_id) > 0 THEN 0 ELSE 1 END,  -- Prima calcolati (0), poi non calcolati (1)
                    ch.start_date ASC NULLS LAST
            ''')
            
            championships = cursor.fetchall()
            
            if not championships:
                print("❌ Nessun campionato con competizioni trovato")
                return
            
            print(f"\n🏆 CAMPIONATI:")
            for champ_id, name, season, start_date, calculated_comps, total_comps, drivers_in_standings in championships:
                season_info = f" ({season})" if season else ""
                standings_status = " ✅ Aggiornata" if drivers_in_standings > 0 else " ⏳ Da calcolare"
                
                # Formato data
                date_str = f" - {start_date[:10]}" if start_date else ""
                
                # Mostra competizioni calcolate/totali
                comp_info = f" - {calculated_comps}/{total_comps} competizioni calcolate"
                
                print(f"  {champ_id}. {name}{season_info}{date_str}{comp_info}{standings_status}")
            
            try:
                champ_id = int(input("\nID campionato: ").strip())
            except ValueError:
                print("❌ ID non valido")
                return
            
            if not any(row[0] == champ_id for row in championships):
                print(f"❌ Campionato non trovato")
                return
            
            conn.close()
            self.calculate_championship_standings(champ_id)
            
        except Exception as e:
            self.logger.error(f"❌ Errore interfaccia calcolo classifica: {e}")

# === FUNZIONE MAIN E SETUP ===

def main():
    """Funzione principale"""
    print("🏁 ACC Server Manager - Championship System")
    print("==========================================")
    
    try:
        # Inizializza gestore campionati (carica automaticamente acc_config.json)
        manager = ChampionshipManager()
        
        print(f"✅ Database caricato: {manager.db_path}")
        print(f"🏆 Community: {manager.config['community']['name']}")
        
        # Avvia menu principale
        manager.show_menu()
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return

if __name__ == "__main__":
    main()