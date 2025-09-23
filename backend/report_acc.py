#!/usr/bin/env python3
"""
ACC Server Reports - Sistema di Report e Statistiche
Generazione report e statistiche per server Assetto Corsa Competizione
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

class ACCReportManager:
    """Classe per la generazione di report ACC"""
    
    def __init__(self, config_file='acc_config.json'):
        """Inizializza il manager dei report"""
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_logging()
        self.db_path = self.config['database']['path']
        
        # Verifica esistenza database
        if not Path(self.db_path).exists():
            print(f"❌ Database not found: {self.db_path}")
            print("Run the main manager first to create the database")
            exit(1)
        
    def load_config(self) -> dict:
        """Carica file di configurazione"""
        if not Path(self.config_file).exists():
            print(f"❌ Configuration file not found: {self.config_file}")
            print("Run the main manager first to create the configuration")
            exit(1)
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def setup_logging(self):
        """Configura il sistema di logging per i report"""
        log_dir = Path(self.config['paths']['logs'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"acc_reports_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"📊 ACC Report Manager avviato - Community: {self.config['community']['name']}")

    # === UTILITÀ ===
    
    def format_lap_time(self, lap_time_ms: Optional[int]) -> str:
        """Converte tempo giro da millisecondi a formato MM:SS.sss - CON FILTRI ANTI-ANOMALIE"""
        if not lap_time_ms or lap_time_ms <= 0:
            return "N/A"
        
        # Filtro valori anomali per tempi giro (> 1 ora = probabilmente dato corrotto)
        if lap_time_ms > 3600000:  # 1 ora in millisecondi
            return "N/A"
        
        # Filtro valori troppo bassi per tempi giro (< 30 secondi = probabilmente errore)
        if lap_time_ms < 30000:  # 30 secondi in millisecondi
            return "N/A"
        
        minutes = lap_time_ms // 60000
        seconds = (lap_time_ms % 60000) / 1000
        return f"{minutes}:{seconds:06.3f}"

    def format_time_duration(self, duration_ms: Optional[int]) -> str:
        """Converte durata da millisecondi a formato MM:SS.sss - SENZA FILTRI (per gap, tempi totali, ecc.)"""
        if duration_ms is None or duration_ms <= 0:
            return "N/A"
        
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) / 1000
        return f"{minutes}:{seconds:06.3f}"

    # === STATISTICHE GENERALI ===
    
    def show_general_statistics(self):
        """Mostra statistiche generali del database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*60}")
            print(f"📊 {self.config['community']['name'].upper()} STATISTICS")
            print(f"{'='*60}")
            
            # Statistiche generali
            cursor.execute('SELECT COUNT(*) FROM sessions')
            total_sessions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM drivers')
            total_drivers = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM laps')
            total_laps = cursor.fetchone()[0]
            
            print(f"\n📈 GENERAL DATA:")
            print(f"  • Total sessions: {total_sessions}")
            print(f"  • Registered drivers: {total_drivers}")
            print(f"  • Total laps: {total_laps}")
            
            # Top vittorie
            cursor.execute('''
                SELECT d.last_name, COUNT(*) as wins
                FROM session_results sr
                JOIN drivers d ON sr.driver_id = d.driver_id
                JOIN sessions s ON sr.session_id = s.session_id
                WHERE sr.position = 1 AND s.session_type LIKE 'R%'
                GROUP BY sr.driver_id
                ORDER BY wins DESC
                LIMIT 10
            ''')
            
            wins = cursor.fetchall()
            if wins:
                print("\n🏆 WINS LEADERBOARD:")
                for i, (name, count) in enumerate(wins, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
                    print(f"  {medal} {i:2d}. {name}: {count} wins")
            
            # Top pole positions
            cursor.execute('''
                SELECT d.last_name, COUNT(*) as poles
                FROM session_results sr
                JOIN drivers d ON sr.driver_id = d.driver_id
                JOIN sessions s ON sr.session_id = s.session_id
                WHERE sr.position = 1 AND s.session_type LIKE 'Q%'
                GROUP BY sr.driver_id
                ORDER BY poles DESC
                LIMIT 10
            ''')
            
            poles = cursor.fetchall()
            if poles:
                print("\n🚀 POLE POSITIONS:")
                for i, (name, count) in enumerate(poles, 1):
                    print(f"   {i:2d}. {name}: {count} poles")
            
            # Record pista
            cursor.execute('''
                SELECT s.track_name, d.last_name, MIN(l.lap_time) as best_lap
                FROM laps l
                JOIN drivers d ON l.driver_id = d.driver_id
                JOIN sessions s ON l.session_id = s.session_id
                WHERE l.is_valid_for_best = 1 AND l.lap_time < 2000000
                GROUP BY s.track_name
                ORDER BY s.track_name
            ''')
            
            records = cursor.fetchall()
            if records:
                print("\n⚡ TRACK RECORDS:")
                for track, driver, lap_time in records:
                    print(f"  {track}: {driver} - {self.format_lap_time(lap_time)}")
            
            # Piloti più attivi
            cursor.execute('''
                SELECT d.last_name, d.total_sessions
                FROM drivers d
                WHERE d.total_sessions > 0
                ORDER BY d.total_sessions DESC
                LIMIT 10
            ''')
            
            active = cursor.fetchall()
            if active:
                print("\n📊 MOST ACTIVE DRIVERS:")
                for i, (name, sessions) in enumerate(active, 1):
                    print(f"   {i:2d}. {name}: {sessions} sessions")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Error generating statistics: {e}")

    # === REPORT PISTA ===
    
    def show_track_report(self):
        """Mostra report dettagliato per pista"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Lista piste
            cursor.execute('SELECT DISTINCT track_name FROM sessions ORDER BY track_name')
            tracks = [row[0] for row in cursor.fetchall()]
            
            if not tracks:
                print("❌ No tracks found in database")
                return
            
            print("\n🏁 AVAILABLE TRACKS:")
            for i, track in enumerate(tracks, 1):
                print(f"  {i:2d}. {track}")
            
            try:
                choice = input(f"\nChoose track (1-{len(tracks)}): ").strip()
                track_idx = int(choice) - 1
                if not 0 <= track_idx < len(tracks):
                    print("❌ Invalid choice")
                    return
                    
                selected_track = tracks[track_idx]
                
            except ValueError:
                print("❌ Invalid input")
                return
            
            # Statistiche pista
            print(f"\n{'='*80}")
            print(f"🏁 TRACK REPORT: {selected_track}")
            print(f"{'='*80}")
            
            # Stats generali
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT s.session_id) as total_sessions,
                    COUNT(DISTINCT l.driver_id) as unique_drivers,
                    COUNT(l.id) as total_laps,
                    MIN(l.lap_time) as best_time,
                    AVG(l.lap_time) as avg_time
                FROM sessions s
                LEFT JOIN laps l ON s.session_id = l.session_id
                WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
            ''', (selected_track,))
            
            stats = cursor.fetchone()
            if stats:
                sessions, drivers, laps, best, avg = stats
                
                # Chi detiene il record
                cursor.execute('''
                    SELECT d.last_name 
                    FROM laps l
                    JOIN drivers d ON l.driver_id = d.driver_id
                    JOIN sessions s ON l.session_id = s.session_id
                    WHERE s.track_name = ? AND l.lap_time = ?
                ''', (selected_track, best))
                
                record_holder = cursor.fetchone()
                record_name = record_holder[0] if record_holder else "N/A"
                
                print(f"\n📊 GENERAL STATISTICS:")
                print(f"  🏆 Absolute record: {self.format_lap_time(best)} - {record_name}")
                print(f"  📈 Average time: {self.format_lap_time(int(avg) if avg else None)}")
                print(f"  🎮 Total sessions: {sessions}")
                print(f"  👥 Unique drivers: {drivers}")
                print(f"  🔄 Valid laps: {laps}")
            
            # Classifica tempi per pilota
            cursor.execute('''
                SELECT 
                    d.last_name,
                    d.short_name,
                    MIN(l.lap_time) as best_lap,
                    COUNT(l.id) as total_laps,
                    s.session_date,
                    s.session_type
                FROM laps l
                JOIN drivers d ON l.driver_id = d.driver_id
                JOIN sessions s ON l.session_id = s.session_id
                WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
                GROUP BY l.driver_id
                ORDER BY best_lap ASC
                LIMIT 20
            ''', (selected_track,))
            
            results = cursor.fetchall()
            if results:
                print(f"\n🏆 BEST TIMES LEADERBOARD BY DRIVER (TOP 20):")
                print(f"{'Pos':<5} {'Time':<10} {'Driver':<25} {'Laps':<8} {'Date':<12} {'Type':<6}")
                print("-" * 76)
                
                for i, (name, short, best_lap, laps, date, session_type) in enumerate(results, 1):
                    # Format date
                    try:
                        date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        date_str = date_obj.strftime('%d/%m/%Y')
                    except:
                        date_str = date[:10] if date else 'N/A'
                    
                    # Session type
                    session_short = {
                            'R1': 'Race', 'R2': 'Race', 'R3': 'Race', 'R4': 'Race', 'R5': 'Race', 
                            'R6': 'Race', 'R7': 'Race', 'R8': 'Race', 'R9': 'Race', 'R': 'Race',
                            'Q1': 'Qual', 'Q2': 'Qual', 'Q3': 'Qual', 'Q4': 'Qual', 'Q5': 'Qual',
                            'Q6': 'Qual', 'Q7': 'Qual', 'Q8': 'Qual', 'Q9': 'Qual', 'Q': 'Qual',
                            'FP1': 'Prac', 'FP2': 'Prac', 'FP3': 'Prac', 'FP4': 'Prac', 'FP5': 'Prac',
                            'FP6': 'Prac', 'FP7': 'Prac', 'FP8': 'Prac', 'FP9': 'Prac', 'FP': 'Prac'
                                }.get(session_type, session_type)
                    
                    # Display name
                    display_name = name[:23] + ".." if len(name) > 25 else name
                    
                    # Medal for top 3 with correct formatting
                    if i == 1:
                        pos_str = "🥇  1 "
                    elif i == 2:
                        pos_str = "🥈  2 "
                    elif i == 3:
                        pos_str = "🥉  3 "
                    else:
                        pos_str = f"   {i:2d} "
                    
                    print(f"{pos_str:<5} {self.format_lap_time(best_lap):<10} {display_name:<25} {laps:<8} {date_str:<12} {session_short:<6}")
                
                # Gap analysis per i primi 10 - USANDO format_time_duration per i gap
                if len(results) > 1:
                    best_time = results[0][2]
                    print(f"\n⏱️  GAP TO LEADER (TOP 10):")
                    print("-" * 40)
                    for i, (name, _, lap_time, _, _, _) in enumerate(results[1:10], 2):
                        gap_ms = lap_time - best_time
                        gap_str = f"+{self.format_time_duration(gap_ms)}"  # USATO format_time_duration
                        display_name = name[:20] + "..." if len(name) > 20 else name
                        print(f"   {i:2d}. {display_name:<25} {gap_str}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Track report error: {e}")

    # === REPORT PILOTA ===
    
    def show_driver_report(self):
        """Mostra report dettagliato per pilota"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Cerca pilota
            search = input("\n🔍 Search driver (name or part): ").strip()
            if not search:
                return
            
            cursor.execute('''
                SELECT driver_id, last_name, short_name, total_sessions, 
                       bad_driver_reports, trust_level, preferred_race_number
                FROM drivers 
                WHERE LOWER(last_name) LIKE ? 
                ORDER BY total_sessions DESC
            ''', (f'%{search.lower()}%',))
            
            drivers = cursor.fetchall()
            
            if not drivers:
                print("❌ No driver found")
                return
            
            if len(drivers) > 1:
                print("\n👥 DRIVERS FOUND:")
                for i, (_, name, _, sessions, _, _, _) in enumerate(drivers, 1):
                    print(f"  {i}. {name} ({sessions} sessions)")
                
                try:
                    choice = int(input(f"\nChoose driver (1-{len(drivers)}): ").strip()) - 1
                    if not 0 <= choice < len(drivers):
                        print("❌ Invalid choice")
                        return
                except ValueError:
                    print("❌ Invalid input")
                    return
            else:
                choice = 0
            
            driver_id, name, short_name, sessions, bad_reports, trust, race_num = drivers[choice]
            
            print(f"\n{'='*60}")
            print(f"👤 DRIVER REPORT: {name}")
            print(f"{'='*60}")
            
            # Info generali
            print(f"\n📊 GENERAL INFORMATION:")
            print(f"  • ID: {driver_id}")
            print(f"  • Short name: {short_name or 'N/A'}")
            print(f"  • Preferred number: #{race_num if race_num else 'N/A'}")
            print(f"  • Total sessions: {sessions}")
            print(f"  • Trust level: {trust}")
            print(f"  • Bad driver reports: {bad_reports}")
            
            # Statistiche generali
            cursor.execute('''
                SELECT 
                    COUNT(CASE WHEN sr.position = 1 AND s.session_type LIKE 'R%' THEN 1 END) as wins,
                    COUNT(CASE WHEN sr.position = 1 AND s.session_type LIKE 'Q%' THEN 1 END) as poles,
                    COUNT(CASE WHEN sr.position <= 3 AND s.session_type LIKE 'R%' THEN 1 END) as podiums,
                    COUNT(DISTINCT s.track_name) as tracks_raced
                FROM session_results sr
                JOIN sessions s ON sr.session_id = s.session_id
                WHERE sr.driver_id = ?
            ''', (driver_id,))
            
            stats = cursor.fetchone()
            if stats:
                wins, poles, podiums, tracks = stats
                print(f"\n🏆 RESULTS:")
                print(f"  • Wins: {wins}")
                print(f"  • Pole positions: {poles}")
                print(f"  • Podiums: {podiums}")
                print(f"  • Tracks raced: {tracks}")
            
            # Best laps per pista
            cursor.execute('''
                SELECT 
                    s.track_name,
                    MIN(l.lap_time) as best_lap,
                    COUNT(l.id) as total_laps
                FROM laps l
                JOIN sessions s ON l.session_id = s.session_id
                WHERE l.driver_id = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
                GROUP BY s.track_name
                ORDER BY s.track_name
            ''', (driver_id,))
            
            track_times = cursor.fetchall()
            if track_times:
                print(f"\n⚡ BEST TIMES BY TRACK:")
                print(f"{'Track':<30} {'Time':<12} {'Total laps':<12}")
                print("-" * 55)
                
                for track, best_lap, laps in track_times:
                    track_display = track[:28] + ".." if len(track) > 30 else track
                    print(f"{track_display:<30} {self.format_lap_time(best_lap):<12} {laps:<12}")
            
            # Verifica record detenuti
            cursor.execute('''
                SELECT s.track_name
                FROM (
                    SELECT track_name, MIN(lap_time) as track_record
                    FROM laps l
                    JOIN sessions s ON l.session_id = s.session_id
                    WHERE l.is_valid_for_best = 1 AND l.lap_time > 0
                    GROUP BY s.track_name
                ) as records
                JOIN sessions s ON s.track_name = records.track_name
                JOIN laps l ON l.session_id = s.session_id AND l.lap_time = records.track_record
                WHERE l.driver_id = ?
            ''', (driver_id,))
            
            records = cursor.fetchall()
            if records:
                print(f"\n🏆 TRACK RECORDS HELD:")
                for (track,) in records:
                    print(f"  • {track}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Driver report error: {e}")

    # === REPORT AVANZATO PISTE ===
    
    def show_advanced_track_report(self):
        """Report pista con più dettagli"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Lista piste con statistiche e detentore record
            cursor.execute('''
                SELECT 
                    s.track_name,
                    COUNT(DISTINCT s.session_id) as sessions,
                    COUNT(DISTINCT sr.driver_id) as drivers,
                    MIN(l.lap_time) as record
                FROM sessions s
                LEFT JOIN session_results sr ON s.session_id = sr.session_id
                LEFT JOIN laps l ON s.session_id = l.session_id AND l.is_valid_for_best = 1
                WHERE l.lap_time > 0
                GROUP BY s.track_name
                ORDER BY sessions DESC
            ''')
            
            tracks = cursor.fetchall()
            
            print(f"\n{'='*100}")
            print(f"📊 ADVANCED TRACKS REPORT")
            print(f"{'='*100}")
            
            print(f"{'Track':<30} {'Sessions':<10} {'Drivers':<8} {'Record':<12} {'Record Holder':<25}")
            print("-" * 100)
            
            for track, sessions, drivers, record in tracks:
                record_str = self.format_lap_time(record) if record else "N/A"
                track_display = track[:28] + ".." if len(track) > 30 else track
                
                # Trova il detentore del record per questa pista
                if record:
                    cursor.execute('''
                        SELECT d.last_name
                        FROM laps l
                        JOIN drivers d ON l.driver_id = d.driver_id
                        JOIN sessions s ON l.session_id = s.session_id
                        WHERE s.track_name = ? AND l.lap_time = ? AND l.is_valid_for_best = 1
                        LIMIT 1
                    ''', (track, record))
                    
                    record_holder = cursor.fetchone()
                    record_name = record_holder[0] if record_holder else "N/A"
                    # Tronca nome se troppo lungo
                    record_name_display = record_name[:23] + ".." if len(record_name) > 25 else record_name
                else:
                    record_name_display = "N/A"
                
                print(f"{track_display:<30} {sessions:<10} {drivers:<8} {record_str:<12} {record_name_display:<25}")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Advanced Report Error: {e}")

    # === REPORT COMPETIZIONI ===
    
    def show_competitions_report(self):
        """Mostra report delle competizioni e campionati"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*80}")
            print(f"🏆 COMPETITIONS AND CHAMPIONSHIPS REPORT")
            print(f"{'='*80}")
            
            # Statistiche generali competizioni
            cursor.execute('SELECT COUNT(*) FROM championships')
            total_championships = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM competitions')
            total_competitions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM sessions WHERE competition_id IS NOT NULL')
            assigned_sessions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM sessions WHERE competition_id IS NULL')
            unassigned_sessions = cursor.fetchone()[0]
            
            print(f"\n📊 GENERAL STATISTICS:")
            print(f"  • Total championships: {total_championships}")
            print(f"  • Total competitions: {total_competitions}")
            print(f"  • Assigned sessions: {assigned_sessions}")
            print(f"  • Unassigned sessions: {unassigned_sessions}")
            
            # Lista campionati con loro competizioni
            cursor.execute('''
                SELECT c.championship_id, c.name, c.season, c.description,
                       COUNT(comp.competition_id) as competitions_count,
                       COUNT(s.session_id) as sessions_count
                FROM championships c
                LEFT JOIN competitions comp ON c.championship_id = comp.championship_id
                LEFT JOIN sessions s ON comp.competition_id = s.competition_id
                GROUP BY c.championship_id
                ORDER BY c.season DESC, c.name
            ''')
            
            championships = cursor.fetchall()
            
            if championships:
                print(f"\n🏆 CHAMPIONSHIPS:")
                for champ_id, name, season, desc, comps, sessions in championships:
                    season_str = f" ({season})" if season else ""
                    print(f"\n🏁 [ID:{champ_id}] {name}{season_str}")
                    if desc:
                        print(f"  📝 {desc}")
                    print(f"  📊 {comps} competitions | {sessions} total sessions")
                    
                    # Mostra competizioni del campionato
                    cursor.execute('''
                        SELECT comp.competition_id, comp.name, comp.track_name, comp.round_number,
                               COUNT(s.session_id) as session_count
                        FROM competitions comp
                        LEFT JOIN sessions s ON comp.competition_id = s.competition_id
                        WHERE comp.championship_id = ?
                        GROUP BY comp.competition_id
                        ORDER BY comp.round_number
                    ''', (champ_id,))
                    
                    competitions = cursor.fetchall()
                    for comp_id, comp_name, track, round_num, sess_count in competitions:
                        round_str = f"Round {round_num}" if round_num else "Round N/A"
                        print(f"    • [ID:{comp_id}] {round_str}: {comp_name} - {track} ({sess_count} sessions)")
            
            # Competizioni libere (senza campionato)
            cursor.execute('''
                SELECT comp.competition_id, comp.name, comp.track_name, comp.weekend_format,
                       COUNT(s.session_id) as session_count
                FROM competitions comp
                LEFT JOIN sessions s ON comp.competition_id = s.competition_id
                WHERE comp.championship_id IS NULL
                GROUP BY comp.competition_id
                ORDER BY comp.created_at DESC
            ''')
            
            free_competitions = cursor.fetchall()
            
            if free_competitions:
                print(f"\n🏁 FREE COMPETITIONS:")
                for comp_id, comp_name, track, weekend_format, sess_count in free_competitions:
                    format_str = f" ({weekend_format})" if weekend_format else ""
                    print(f"  • [ID:{comp_id}] {comp_name} - {track}{format_str} ({sess_count} sessions)")
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Competition report error: {e}")
            
    # === REPORT COMPETIZIONI AVANZATO ===            
    
    def show_advanced_competition_report(self):
        """Report avanzato per una competizione specifica"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n{'='*80}")
            print(f"🏆 ADVANCED COMPETITIONS REPORT")
            print(f"{'='*80}")
            
            # Offri scelta del metodo di selezione
            print("\n📋 COMPETITION SELECTION METHOD:")
            print("  1. Enter competition ID")
            print("  2. Choose from completed competitions list")
            print("  0. Return to main menu")
            
            selection_method = input("\nChoice: ").strip()
            
            if selection_method == "0":
                conn.close()
                return
            elif selection_method == "1":
                competition_id = self._select_competition_by_id(cursor)
            elif selection_method == "2":
                competition_id = self._select_competition_from_completed_list(cursor)
            else:
                print("❌ Invalid choice")
                conn.close()
                return
            
            if not competition_id:
                conn.close()
                return
            
            # Genera il report per la competizione selezionata
            self._generate_competition_report(cursor, competition_id)
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Advanced Competition Report Error: {e}")

    def _select_competition_by_id(self, cursor) -> Optional[int]:
        """Selezione competizione tramite inserimento ID"""
        try:
            comp_id_input = input("\n🔍 Enter competition ID: ").strip()
            
            if not comp_id_input.isdigit():
                print("❌ Invalid ID")
                return None
            
            competition_id = int(comp_id_input)
            
            # Verifica esistenza competizione
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.is_completed,
                       ch.name as championship_name, ch.season
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Competition with ID {competition_id} not found")
                return None
            
            comp_id, comp_name, track, is_completed, champ_name, season = result
            
            # Mostra info competizione trovata
            champ_info = f"{champ_name} ({season})" if champ_name else "Free competition"
            status = "✅ Completed" if is_completed else "🔄 In progress"
            
            print(f"\n📋 COMPETITION FOUND:")
            print(f"  • Name: {comp_name}")
            print(f"  • Track: {track}")
            print(f"  • Championship: {champ_info}")
            print(f"  • Status: {status}")
            
            confirm = input("\n❓ Proceed with this competition? (y/N): ").strip().lower()
            if confirm in ['s', 'si', 'sì', 'y', 'yes']:
                return competition_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ ID selection error: {e}")
            return None

    def _select_competition_from_completed_list(self, cursor) -> Optional[int]:
        """Selezione competizione da elenco delle completate"""
        try:
            # Recupera competizioni completate
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.round_number,
                       ch.name as championship_name, ch.season,
                       COUNT(s.session_id) as session_count
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                LEFT JOIN sessions s ON c.competition_id = s.competition_id
                WHERE c.is_completed = 1
                GROUP BY c.competition_id
                ORDER BY ch.season DESC, c.round_number, c.name
            ''')
            
            completed_competitions = cursor.fetchall()
            
            if not completed_competitions:
                print("\n❌ No completed competitions found")
                return None
            
            print(f"\n🏁 COMPLETED COMPETITIONS ({len(completed_competitions)}):")
            print(f"{'#':<4} {'Name':<30} {'Track':<25} {'Championship':<25} {'Sessions':<10}")
            print("-" * 100)
            
            for i, (comp_id, comp_name, track, round_num, champ_name, season, session_count) in enumerate(completed_competitions, 1):
                # Prepara visualizzazione
                comp_display = comp_name[:28] + ".." if len(comp_name) > 30 else comp_name
                track_display = track[:23] + ".." if len(track) > 25 else track
                
                if champ_name:
                    champ_display = f"{champ_name} ({season})" if season else champ_name
                    champ_display = champ_display[:23] + ".." if len(champ_display) > 25 else champ_display
                else:
                    champ_display = "Free competition"
                
                print(f"{i:<4} {comp_display:<30} {track_display:<25} {champ_display:<25} {session_count:<10}")
            
            # Selezione
            try:
                choice = input(f"\nChoose competition (1-{len(completed_competitions)}): ").strip()
                choice_int = int(choice) - 1
                
                if 0 <= choice_int < len(completed_competitions):
                    return completed_competitions[choice_int][0]  # competition_id
                else:
                    print("❌ Invalid choice")
                    return None
                    
            except ValueError:
                print("❌ Invalid input")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error selecting from list: {e}")
            return None

    def _generate_competition_report(self, cursor, competition_id: int):
        """Genera il report completo per una competizione (riutilizzabile per report campionato)"""
        try:
            # Recupera info competizione
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.round_number,
                       c.date_start, c.date_end, c.weekend_format,
                       ch.name as championship_name, ch.season
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            comp_info = cursor.fetchone()
            if not comp_info:
                print("❌ Competition not found")
                return
            
            comp_id, comp_name, track, round_num, date_start, date_end, weekend_format, champ_name, season = comp_info
            
            # Header competizione
            print(f"\n{'='*100}")
            round_str = f"Round {round_num} - " if round_num else ""
            print(f"🏆 {round_str}{comp_name}")
            print(f"{'='*100}")
            
            print(f"\n📋 COMPETITION INFORMATION:")
            print(f"  • ID: {comp_id}")
            print(f"  • Track: {track}")
            if champ_name:
                champ_info = f"{champ_name} ({season})" if season else champ_name
                print(f"  • Championship: {champ_info}")
            print(f"  • Dates: {date_start} - {date_end}")
            print(f"  • Format: {weekend_format}")
            
            # Recupera sessioni della competizione
            cursor.execute('''
                SELECT s.session_id, s.session_type, s.session_date, s.session_order,
                       s.total_drivers, s.best_lap_overall
                FROM sessions s
                WHERE s.competition_id = ?
                ORDER BY s.session_order, s.session_date
            ''', (competition_id,))
            
            sessions = cursor.fetchall()
            
            if not sessions:
                print("\n❌ No sessions found for this competition")
                return
            
            print(f"\n🎮 COMPETITION SESSIONS ({len(sessions)}):")
            
            # Processa ogni sessione
            for session_id, session_type, session_date, session_order, total_drivers, best_lap_overall in sessions:
                self._generate_session_results_report(cursor, session_id, session_type, session_date, total_drivers, best_lap_overall)
            
            # Report penalità per tutta la competizione
            self._generate_competition_penalties_report(cursor, competition_id)
            
        except Exception as e:
            self.logger.error(f"❌ Competition report generation error: {e}")

    def _generate_session_results_report(self, cursor, session_id: str, session_type: str, 
                                       session_date: str, total_drivers: int, best_lap_overall: Optional[int]):
        """Genera il report risultati per una singola sessione"""
        try:
            # Format data
            try:
                date_obj = datetime.fromisoformat(session_date.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%d/%m/%Y %H:%M')
            except:
                date_str = session_date[:16] if session_date else 'N/A'
            
            print(f"\n{'─' * 87}")
            print(f"🏁 {session_type} - {date_str} ({total_drivers} drivers)")
            print(f"{'─' * 87}")
            
            # Recupera risultati sessione con best lap
            cursor.execute('''
                SELECT sr.position, sr.race_number, d.last_name, d.short_name,
                       sr.lap_count, sr.best_lap, sr.total_time,
                       d.driver_id
                FROM session_results sr
                JOIN drivers d ON sr.driver_id = d.driver_id
                WHERE sr.session_id = ?
                ORDER BY sr.position
            ''', (session_id,))
            
            results = cursor.fetchall()
            
            if not results:
                print("❌ No results found for this session")
                return
            
            # Trova il miglior giro della sessione
            session_best_lap = None
            if best_lap_overall:
                session_best_lap = best_lap_overall
            else:
                # Calcola dal database se non disponibile
                cursor.execute('''
                    SELECT MIN(lap_time) 
                    FROM laps 
                    WHERE session_id = ? AND is_valid_for_best = 1 AND lap_time > 0
                ''', (session_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    session_best_lap = result[0]
            
            # Header tabella risultati
            print(f"{'Pos':<4} {'Num':<5} {'Driver':<25} {'Laps':<6} {'Best Lap':<13} {'Total Time':<13} {'Notes':<10}")
            print("─" * 87)
            
            # Visualizza risultati
            for position, race_number, last_name, short_name, lap_count, best_lap, total_time, driver_id in results:
                # Nome pilota
                display_name = last_name[:23] + ".." if len(last_name) > 25 else last_name
                
                # Miglior giro - gestione valori sballati
                if best_lap and best_lap > 0 and best_lap < 10000000:  # Filtro valori ragionevoli
                    best_lap_str = self.format_lap_time(best_lap)
                else:
                    best_lap_str = "N/A"
                
                # Tempo totale - gestione valori sballati - USANDO format_time_duration
                if total_time and total_time > 0 and total_time < 86400000:  # Filtro < 24 ore
                    total_time_str = self.format_time_duration(total_time)  # USATO format_time_duration
                else:
                    total_time_str = "N/A"
                
                # Numero gara
                race_num_str = f"{race_number:03d}" if race_number else "000"
                                   
                # Posizione con medaglie
                if position == 1:
                    pos_str = "🥇 1"
                elif position == 2:
                    pos_str = "🥈 2"
                elif position == 3:
                    pos_str = "🥉 3"
                else:
                    pos_str = f"{position:>4}"
                    
                # Note - fulmine per best lap
                notes = ""
                if best_lap and session_best_lap and best_lap == session_best_lap:
                    notes = "⚡ BEST"
                
                # Stampa con allineamento corretto
                if position <= 3:
                    print(f"{pos_str} {race_num_str:<5} {display_name:<25} {lap_count:<6} {best_lap_str:<13} {total_time_str:<13} {notes:<10}")
                else:
                    print(f"{pos_str:<4} {race_num_str:<5} {display_name:<25} {lap_count:<6} {best_lap_str:<13} {total_time_str:<13} {notes:<10}")
            
            # Mostra miglior giro della sessione se disponibile
            if session_best_lap:
                print(f"\n⚡ Session best lap: {self.format_lap_time(session_best_lap)}")
            
        except Exception as e:
            self.logger.error(f"❌ Session report error {session_id}: {e}")

    def _generate_competition_penalties_report(self, cursor, competition_id: int):
        """Genera il report penalità per tutta la competizione"""
        try:
            # Recupera tutte le penalità della competizione
            cursor.execute('''
                SELECT p.session_id, s.session_type, d.last_name, d.short_name,
                       p.reason, p.penalty_type, p.penalty_value, p.violation_lap,
                       p.cleared_lap, p.is_post_race, p.car_id
                FROM penalties p
                JOIN sessions s ON p.session_id = s.session_id
                JOIN drivers d ON p.driver_id = d.driver_id
                WHERE s.competition_id = ?
                ORDER BY s.session_order, s.session_date, p.violation_lap
            ''', (competition_id,))
            
            penalties = cursor.fetchall()
            
            if not penalties:
                print(f"\n✅ NO PENALTIES RECORDED FOR THIS COMPETITION")
                return
            
            print(f"\n{'='*100}")
            print(f"🚨 COMPETITION PENALTIES ({len(penalties)} penalties)")
            print(f"{'='*100}")
            
            # Raggruppa per sessione
            current_session = None
            session_penalty_count = 0
            
            for penalty in penalties:
                session_id, session_type, last_name, short_name, reason, penalty_type, penalty_value, violation_lap, cleared_lap, is_post_race, car_id = penalty
                
                # Nuovo header per nuova sessione
                if current_session != session_id:
                    if current_session is not None:
                        print(f"  └─ Total session penalties: {session_penalty_count}")
                    
                    current_session = session_id
                    session_penalty_count = 0
                    print(f"\n🏁 {session_type}:")
                    print(f"{'Driver':<25} {'Reason':<30} {'Penalty':<15} {'Lap':<8} {'Type':<12}")
                    print("─" * 95)
                
                session_penalty_count += 1
                
                # Nome pilota
                display_name = last_name
                display_name = display_name[:23] + ".." if len(display_name) > 25 else display_name
                
                # Motivo
                reason_display = reason[:28] + ".." if len(reason) > 30 else reason
                
                # Tipo penalità con valore
                if penalty_value and penalty_value > 0:
                    penalty_display = f"{penalty_type} {penalty_value}s"
                else:
                    penalty_display = penalty_type
                penalty_display = penalty_display[:13] + ".." if len(penalty_display) > 15 else penalty_display
                
                # Giro
                lap_info = f"L{violation_lap}" if violation_lap else "N/A"
                if cleared_lap and cleared_lap != violation_lap:
                    lap_info += f"-{cleared_lap}"
                
                # Tipo (in gara vs post-gara)
                penalty_timing = "Post-race" if is_post_race else "In-race"
                
                print(f"{display_name:<25} {reason_display:<30} {penalty_display:<15} {lap_info:<8} {penalty_timing:<12}")
            
            # Ultima sessione
            if current_session is not None:
                print(f"  ")
                print(f"└─ Total session penalties: {session_penalty_count}")
            
        except Exception as e:
            self.logger.error(f"❌ Competition Penalty Report Error: {e}")
            
    def show_menu(self):
        """Mostra menu principale dei report"""
        while True:
            print(f"\n{'='*60}")
            print(f"📊 ACC REPORT MANAGER - {self.config['community']['name']}")
            print(f"{'='*60}")
            print("\n📋 REPORTS MENU:")
            print("  1. View general statistics")
            print("  2. Detailed track report")
            print("  3. Detailed driver report")
            print("  4. Advanced tracks report")
            print("  5. Competitions and championships report")
            print("  6. Advanced competitions report")
            print("  0. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                self.show_general_statistics()
            elif choice == "2":
                self.show_track_report()
            elif choice == "3":
                self.show_driver_report()
            elif choice == "4":
                self.show_advanced_track_report()
            elif choice == "5":
                self.show_competitions_report()
            elif choice == "6":
                self.show_advanced_competition_report()
            elif choice == "0":
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice")
            
            if choice != "0":
                input("\n↩️  Press ENTER to continue...")

def main():
    """Funzione principale"""
    try:
        print("📊 ACC Report Manager")
        print("Initializing...\n")
        
        report_manager = ACCReportManager()
        report_manager.show_menu()
        
    except KeyboardInterrupt:
        print("\n\n⛔ Operation interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()