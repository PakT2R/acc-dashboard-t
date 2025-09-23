#!/usr/bin/env python3
"""
ACC Mobile Reports Suite - Versione completa ottimizzata per smartphone
Tutti i report con output max 38-40 caratteri per riga
Perfetto per Discord Bot e utilizzo mobile
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

class ACCMobileReporter:
    """Suite completa di report ACC ottimizzati per mobile"""
    
    MAX_LINE_LENGTH = 40
    
    def __init__(self, config_file='acc_config.json'):
        """Inizializza il reporter mobile"""
        self.config_file = config_file
        self.config = self.load_config()
        self.db_path = self.config['database']['path']
        
        # Verifica esistenza database
        if not Path(self.db_path).exists():
            print("❌ Database not found")
            print("Run main manager first")
            exit(1)
        
    def load_config(self) -> dict:
        """Carica file di configurazione"""
        if not Path(self.config_file).exists():
            print("❌ Config file not found")
            exit(1)
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # === UTILITÀ COMUNI ===
    
    def format_lap_time(self, lap_time_ms: Optional[int]) -> str:
        """Converte tempo giro con filtri anti-anomalie"""
        if not lap_time_ms or lap_time_ms <= 0:
            return "N/A"
        
        # Filtri anomalie
        if lap_time_ms > 3600000 or lap_time_ms < 30000:
            return "N/A"
        
        minutes = lap_time_ms // 60000
        seconds = (lap_time_ms % 60000) / 1000
        return f"{minutes}:{seconds:06.3f}"

    def format_time_duration(self, duration_ms: Optional[int]) -> str:
        """Converte durata per gap e tempi totali"""
        if duration_ms is None or duration_ms <= 0:
            return "N/A"
        
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) / 1000
        return f"{minutes}:{seconds:06.3f}"

    def truncate_text(self, text: str, max_length: int) -> str:
        """Tronca testo se troppo lungo"""
        if len(text) <= max_length:
            return text
        return text[:max_length-2] + ".."

    def print_header(self, title: str, char: str = "="):
        """Stampa header formattato"""
        print(f"\n{title}")
        print(char * self.MAX_LINE_LENGTH)

    def print_separator(self, char: str = "-"):
        """Stampa separatore"""
        print(char * self.MAX_LINE_LENGTH)

    # === 1. STATISTICHE GENERALI ===
    
    def show_mobile_general_statistics(self):
        """Statistiche generali formato mobile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            community_name = self.config['community']['name']
            short_name = self.truncate_text(community_name, 25)
            
            self.print_header(f"📊 {short_name} STATS")
            
            # Dati generali base
            cursor.execute('SELECT COUNT(*) FROM sessions')
            total_sessions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM drivers')
            total_drivers = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM laps')
            total_laps = cursor.fetchone()[0]
            
            # Dati aggiuntivi dal dashboard
            cursor.execute('SELECT COUNT(*) FROM championships WHERE is_completed = 1')
            total_championships = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM competitions 
                             WHERE is_completed = 1 AND championship_id is not null''')
            completed_competitions = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM sessions s 
                             WHERE s.competition_id IS NOT NULL AND EXISTS
                             (SELECT 1 FROM competitions c 
                              WHERE c.competition_id = s.competition_id 
                              AND c.championship_id IS NOT NULL)''')
            championship_sessions = cursor.fetchone()[0]
            
            # Calcola media giri per sessione
            avg_laps = round(total_laps / total_sessions, 1) if total_sessions > 0 else 0
            
            # Ultima sessione campionato
            cursor.execute('''SELECT MAX(session_date) FROM sessions s 
                             WHERE s.competition_id IS NOT NULL AND EXISTS
                             (SELECT 1 FROM competitions c 
                              WHERE c.competition_id = s.competition_id 
                              AND c.championship_id IS NOT NULL)''')
            last_session_result = cursor.fetchone()
            last_session = last_session_result[0] if last_session_result else None
            
            print("\n📈 GENERAL DATA")
            self.print_separator()
            print(f"👥 Registered drivers: {total_drivers}")
            print(f"🎮 Total sessions: {total_sessions}")
            print(f"🔄 Total laps: {total_laps:,}")
            print(f"📊 Average laps/session: {avg_laps}")
            
            print(f"\n🏆 CHAMPIONSHIP DATA")
            self.print_separator()
            print(f"🏆 Completed championships: {total_championships}")
            print(f"🏁 Championship competitions: {completed_competitions}")
            print(f"🎯 Championship sessions: {championship_sessions}")
            
            # Ultima sessione
            if last_session:
                try:
                    from datetime import datetime
                    last_date = datetime.fromisoformat(last_session.replace('Z', '+00:00'))
                    days_ago = (datetime.now() - last_date).days
                    if days_ago == 0:
                        last_text = "Today"
                    elif days_ago == 1:
                        last_text = "Yesterday"
                    else:
                        last_text = f"{days_ago} days ago"
                    print(f"⏰ Last session: {last_text}")
                except:
                    print(f"⏰ Last session: N/A")
            
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
                print(f"\n🏆 WINS LEADERBOARD")
                self.print_separator()
                
                for i, (name, count) in enumerate(wins, 1):
                    if i == 1:
                        medal = "🥇"
                    elif i == 2:
                        medal = "🥈"
                    elif i == 3:
                        medal = "🥉"
                    else:
                        medal = f"{i:2d}"
                    
                    name_display = self.truncate_text(name, 20)
                    print(f"{medal} {name_display:<20} 🏆 {count} wins")
            
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
                print(f"\n🚀 POLE POSITIONS")
                self.print_separator()
                
                for i, (name, count) in enumerate(poles, 1):
                    name_display = self.truncate_text(name, 20)
                    print(f"{i:2d}. {name_display:<20} 🚀 {count} poles")
            
            # Record piste
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
                print(f"\n⚡ TRACK RECORDS")
                self.print_separator()
                
                for track, driver, lap_time in records:
                    track_display = self.truncate_text(track, 18)
                    driver_display = self.truncate_text(driver, 15)
                    time_str = self.format_lap_time(lap_time)
                    
                    print(f"🏁 {track_display:<18} ⚡ {time_str} 👤 {driver_display}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Stats error: {e}")

    # === 2. REPORT PISTE ===
    
    def show_tracks_list_mobile(self):
        """Lista piste in formato mobile - solo con giri validi"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Solo piste con giri validi
            cursor.execute('''
                SELECT DISTINCT s.track_name 
                FROM sessions s
                JOIN laps l ON s.session_id = l.session_id
                WHERE l.is_valid_for_best = 1 AND l.lap_time > 0
                ORDER BY s.track_name
            ''')
            tracks = [row[0] for row in cursor.fetchall()]
            
            if not tracks:
                print("❌ No tracks found")
                return None
            
            self.print_header("🏁 AVAILABLE TRACKS")
            
            for i, track in enumerate(tracks, 1):
                track_display = self.truncate_text(track, 32)
                print(f"{i:2d}. {track_display}")
            
            self.print_separator()
            
            try:
                choice = input(f"Choose track (1-{len(tracks)}): ").strip()
                track_idx = int(choice) - 1
                if 0 <= track_idx < len(tracks):
                    conn.close()
                    return tracks[track_idx]
                else:
                    print("❌ Invalid choice")
                    return None
                    
            except ValueError:
                print("❌ Invalid input")
                return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def show_mobile_track_report(self):
        """Report pista dettagliato per mobile"""
        selected_track = self.show_tracks_list_mobile()
        
        if not selected_track:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Header del report
            track_name = self.truncate_text(selected_track, 35)
            self.print_header(f"🏁 {track_name}")
            
            # Statistiche generali
            self._show_mobile_track_stats(cursor, selected_track)
            
            # Verifica se ci sono giri validi prima di continuare
            cursor.execute('''
                SELECT COUNT(l.id) 
                FROM sessions s
                JOIN laps l ON s.session_id = l.session_id
                WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
            ''', (selected_track,))
            
            valid_laps = cursor.fetchone()[0]
            if valid_laps == 0:
                print("\n⚠️  No data available for detailed report")
                conn.close()
                return
            
            # Record assoluto
            self._show_mobile_track_record(cursor, selected_track)
            
            # Classifica piloti
            self._show_mobile_drivers_ranking(cursor, selected_track)
            
            # Gap analysis
            self._show_mobile_gap_analysis(cursor, selected_track)
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Report error: {e}")

    def _show_mobile_track_stats(self, cursor, track_name: str):
        """Statistiche generali pista formato mobile"""
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT s.session_id) as sessions,
                COUNT(DISTINCT l.driver_id) as drivers,
                COUNT(l.id) as laps,
                AVG(l.lap_time) as avg_time
            FROM sessions s
            LEFT JOIN laps l ON s.session_id = l.session_id
            WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
        ''', (track_name,))
        
        stats = cursor.fetchone()
        if stats:
            sessions, drivers, laps, avg = stats
            
            # Verifica che ci siano giri validi
            if laps == 0:
                print("\n⚠️  No valid laps found")
                print("This track has no recorded data.")
                return
            
            avg_formatted = self.format_lap_time(int(avg) if avg else None)
            
            print("\n📊 GENERAL STATS")
            self.print_separator()
            print(f"🎮 Sessions: {sessions}")
            print(f"👥 Drivers: {drivers}")
            print(f"🔄 Valid laps: {laps}")
            print(f"📈 Average: {avg_formatted}")

    def _show_mobile_track_record(self, cursor, track_name: str):
        """Record pista formato mobile"""
        cursor.execute('''
            SELECT 
                MIN(l.lap_time) as record,
                d.last_name,
                s.session_date,
                s.session_type
            FROM laps l
            JOIN drivers d ON l.driver_id = d.driver_id
            JOIN sessions s ON l.session_id = s.session_id
            WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
        ''', (track_name,))
        
        result = cursor.fetchone()
        if result:
            record, driver, date, session_type = result
            
            # Format date
            try:
                date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%d/%m/%Y')
            except:
                date_str = date[:10] if date else 'N/A'
            
            # Session type short
            session_short = {
                'R1': 'Race', 'R2': 'Race', 'R': 'Race',
                'Q1': 'Qual', 'Q2': 'Qual', 'Q': 'Qual',
                'FP1': 'Prac', 'FP2': 'Prac', 'FP': 'Prac'
            }.get(session_type, session_type[:4])
            
            driver_display = self.truncate_text(driver, 20)
            
            print(f"\n🏆 TRACK RECORD")
            self.print_separator()
            print(f"⚡ {self.format_lap_time(record)}")
            print(f"👤 {driver_display}")
            print(f"📅 {date_str} ({session_short})")

    def _show_mobile_drivers_ranking(self, cursor, track_name: str):
        """Classifica piloti formato mobile"""
        cursor.execute('''
            SELECT 
                d.last_name,
                MIN(l.lap_time) as best_lap,
                s.session_date,
                s.session_type,
                s.competition_id
            FROM laps l
            JOIN drivers d ON l.driver_id = d.driver_id
            JOIN sessions s ON l.session_id = s.session_id
            WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
            GROUP BY l.driver_id
            ORDER BY best_lap ASC
            LIMIT 15
        ''', (track_name,))
        
        results = cursor.fetchall()
        if results:
            print(f"\n🏆 TOP DRIVERS (15)")
            print("🟢 = Official | ⚪ = Unofficial")
            self.print_separator()
            
            for i, (name, best_lap, session_date, session_type, competition_id) in enumerate(results, 1):
                # Medal for top 3
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈" 
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"{i:2d}"
                
                name_display = self.truncate_text(name, 15)
                time_str = self.format_lap_time(best_lap)
                
                # Format date
                try:
                    date_obj = datetime.fromisoformat(session_date.replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%d/%m/%y')
                except:
                    date_str = session_date[:8] if session_date else 'N/A'
                
                # Session type and official indicator
                session_short = session_type if session_type else 'N/A'
                session_padded = f"{session_short:<3}"  # Fixed width of 3 characters
                dot_indicator = "🟢" if competition_id is not None else "⚪"
                
                # Tutto su una singola riga con formattazione in colonne
                print(f"{medal} {name_display:<15} {time_str} {dot_indicator} {date_str} {session_padded}")

    def _show_mobile_gap_analysis(self, cursor, track_name: str):
        """Gap analysis formato mobile"""
        cursor.execute('''
            SELECT 
                d.last_name,
                MIN(l.lap_time) as best_lap
            FROM laps l
            JOIN drivers d ON l.driver_id = d.driver_id
            JOIN sessions s ON l.session_id = s.session_id
            WHERE s.track_name = ? AND l.is_valid_for_best = 1 AND l.lap_time > 0
            GROUP BY l.driver_id
            ORDER BY best_lap ASC
            LIMIT 10
        ''', (track_name,))
        
        results = cursor.fetchall()
        if len(results) > 1:
            best_time = results[0][1]
            
            print(f"\n⏱️  GAP TO LEADER (TOP 10)")
            self.print_separator()
            
            # Leader - tutto su una riga
            leader_name = self.truncate_text(results[0][0], 30)
            print(f"🥇  {leader_name:<25} {self.format_lap_time(best_time)} ⚡")
            
            # Others with gaps - tutto su una riga
            for i, (name, lap_time) in enumerate(results[1:10], 2):
                gap_ms = lap_time - best_time
                gap_str = f"+{self.format_time_duration(gap_ms)}"
                name_display = self.truncate_text(name, 25)
                
                print(f"{i:2d}. {name_display:<25} {gap_str}")
 
 # === 4. REPORT PILOTI ===
    
    def show_mobile_driver_report(self):
        """Report pilota dettagliato per mobile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Cerca pilota
            search = input("\n🔍 Search driver (name): ").strip()
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
                self.print_header("👥 DRIVERS FOUND")
                for i, (_, name, _, sessions, _, _, _) in enumerate(drivers, 1):
                    name_display = self.truncate_text(name, 25)
                    print(f"{i}. {name_display} ({sessions})")
                
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
            
            # Header pilota
            name_display = self.truncate_text(name, 30)
            self.print_header(f"👤 {name_display}")
            
            # Info generali
            print("\n📊 GENERAL INFO")
            self.print_separator()
            print(f"🆔 ID: {driver_id}")
            print(f"📛 Short: {short_name or 'N/A'}")
            print(f"🔢 Number: #{race_num if race_num else 'N/A'}")
            print(f"🎮 Sessions: {sessions}")
            print(f"⭐ Trust: {trust}")
            print(f"⚠️  Reports: {bad_reports}")
            
            # Statistiche risultati
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
                print(f"\n🏆 RESULTS")
                self.print_separator()
                print(f"🏆 Wins: {wins}")
                print(f"🚀 Poles: {poles}")
                print(f"🏅 Podiums: {podiums}")
                print(f"🏁 Tracks: {tracks}")
            
            # Best laps per pista (top 10)
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
                LIMIT 10
            ''', (driver_id,))
            
            track_times = cursor.fetchall()
            if track_times:
                print(f"\n⚡ BEST TIMES (TOP 10)")
                self.print_separator()
                
                for track, best_lap, laps in track_times:
                    track_display = self.truncate_text(track, 25)
                    time_str = self.format_lap_time(best_lap)
                    
                    print(f"🏁 {track_display}")
                    print(f"   ⚡ {time_str} ({laps} laps)")
                    print()
            
            # Record detenuti
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
                print(f"\n🏆 TRACK RECORDS HELD")
                self.print_separator()
                for (track,) in records:
                    track_display = self.truncate_text(track, 32)
                    print(f"⚡ {track_display}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Driver report error: {e}")

    # === 5. REPORT COMPETIZIONI ===

    def show_mobile_advanced_competition_report(self):
        """Report competizione avanzato per mobile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            self.print_header("🏆 ADVANCED COMPETITION REPORT")
            
            print("\n📋 SELECTION METHOD:")
            print("  1. Enter competition ID")
            print("  2. Choose from completed list")
            print("  0. Return to menu")
            
            selection_method = input("\nChoice: ").strip()
            
            if selection_method == "0":
                conn.close()
                return
            elif selection_method == "1":
                competition_id = self._select_competition_by_id_mobile(cursor)
            elif selection_method == "2":
                competition_id = self._select_competition_from_list_mobile(cursor)
            else:
                print("❌ Invalid choice")
                conn.close()
                return
            
            if not competition_id:
                conn.close()
                return
            
            # Genera report competizione
            self._generate_mobile_competition_report(cursor, competition_id)
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Advanced competition error: {e}")

    def _select_competition_by_id_mobile(self, cursor) -> Optional[int]:
        """Selezione competizione per ID mobile"""
        try:
            comp_id_input = input("\n🔍 Enter competition ID: ").strip()
            
            if not comp_id_input.isdigit():
                print("❌ Invalid ID")
                return None
            
            competition_id = int(comp_id_input)
            
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.is_completed,
                       ch.name as championship_name, ch.season
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Competition {competition_id} not found")
                return None
            
            comp_id, comp_name, track, is_completed, champ_name, season = result
            
            comp_display = self.truncate_text(comp_name, 30)
            track_display = self.truncate_text(track, 25)
            champ_info = f"{champ_name} ({season})" if champ_name else "Free"
            champ_display = self.truncate_text(champ_info, 25)
            status = "✅ Completed" if is_completed else "🔄 In progress"
            
            print(f"\n📋 COMPETITION FOUND")
            self.print_separator()
            print(f"📛 {comp_display}")
            print(f"🏁 {track_display}")
            print(f"🏆 {champ_display}")
            print(f"📊 {status}")
            
            confirm = input("\n❓ Proceed? (y/N): ").strip().lower()
            if confirm in ['s', 'si', 'sì', 'y', 'yes']:
                return competition_id
            
            return None
            
        except Exception as e:
            print(f"❌ ID selection error: {e}")
            return None

    def _select_competition_from_list_mobile(self, cursor) -> Optional[int]:
        """Selezione competizione da lista mobile"""
        try:
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
                LIMIT 20
            ''')
            
            completed_competitions = cursor.fetchall()
            
            if not completed_competitions:
                print("\n❌ No completed competitions found")
                return None
            
            self.print_header(f"🏁 COMPLETED ({len(completed_competitions)})")
            
            for i, (comp_id, comp_name, track, round_num, champ_name, season, session_count) in enumerate(completed_competitions, 1):
                comp_display = self.truncate_text(comp_name, 25)
                track_display = self.truncate_text(track, 20)
                
                if champ_name:
                    # Aumentato a 30 caratteri per il nome del campionato
                    champ_display = f"{champ_name} ({season})" if season else champ_name
                    champ_display = self.truncate_text(champ_display, 30)
                else:
                    champ_display = "Free"
                
                print(f"{i:2d}. {comp_display}")
                print(f"    🏁 {track_display}")
                print(f"    🏆 {champ_display}")
                print(f"    🎮 {session_count} sessions")
                print()
            
            try:
                choice = input(f"Choose (1-{len(completed_competitions)}): ").strip()
                choice_int = int(choice) - 1
                
                if 0 <= choice_int < len(completed_competitions):
                    return completed_competitions[choice_int][0]
                else:
                    print("❌ Invalid choice")
                    return None
                    
            except ValueError:
                print("❌ Invalid input")
                return None
                
        except Exception as e:
            print(f"❌ List selection error: {e}")
            return None

    def _generate_mobile_competition_report(self, cursor, competition_id: int):
        """Genera report competizione mobile"""
        try:
            # Info competizione - QUERY CORRETTA con date campionato
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.round_number,
                       c.date_start as competition_date_start, c.date_end, c.weekend_format,
                       ch.name as championship_name, ch.season,
                       ch.start_date as championship_date_start, ch.end_date as championship_date_end
                FROM competitions c
                LEFT JOIN championships ch ON c.championship_id = ch.championship_id
                WHERE c.competition_id = ?
            ''', (competition_id,))
            
            comp_info = cursor.fetchone()
            if not comp_info:
                print("❌ Competition not found")
                return
            
            (comp_id, comp_name, track, round_num, comp_date_start, date_end, weekend_format, 
             champ_name, season, champ_date_start, champ_date_end) = comp_info
            
            # Header competizione
            comp_display = self.truncate_text(comp_name, 30)
            round_str = f"R{round_num} - " if round_num else ""
            self.print_header(f"🏆 {round_str}{comp_display}")
            
            print("\n📋 COMPETITION INFO")
            self.print_separator()
            print(f"🆔 ID: {comp_id}")
            
            # MODIFICA: Track + data competizione (riga 818)
            track_display = self.truncate_text(track, 25)  # Ridotto per fare spazio alla data
            if comp_date_start:
                comp_date_str = comp_date_start[:10]  # Solo YYYY-MM-DD
                print(f"🏁 {track_display} ({comp_date_str})")
            else:
                print(f"🏁 {track_display}")
                
            if champ_name:
                champ_info = f"{champ_name} ({season})" if season else champ_name
                champ_display = self.truncate_text(champ_info, 30)
                print(f"🏆 {champ_display}")
                
                # MODIFICA: Date del CAMPIONATO (non della competizione)
                if champ_date_start and champ_date_end:
                    print(f"📅 {champ_date_start[:10]} - {champ_date_end[:10]}")
                    
            if weekend_format:
                format_display = self.truncate_text(weekend_format, 30)
                print(f"📋 {format_display}")
            
            # Sessioni
            cursor.execute('''
                SELECT s.session_id, s.session_type, s.session_date, s.session_order,
                       s.total_drivers, s.best_lap_overall
                FROM sessions s
                WHERE s.competition_id = ?
                ORDER BY s.session_order, s.session_date
            ''', (competition_id,))
            
            sessions = cursor.fetchall()
            
            if not sessions:
                print("\n❌ No sessions found")
                return
            
            print(f"🎮 {len(sessions)} sessions")
            
            for session_id, session_type, session_date, session_order, total_drivers, best_lap_overall in sessions:
                self._generate_mobile_session_report(cursor, session_id, session_type, session_date, total_drivers, best_lap_overall)
            
            # Classifica punti
            self._generate_mobile_competition_points_report(cursor, competition_id)
            
            # Penalità
            self._generate_mobile_penalties_report(cursor, competition_id)
            
        except Exception as e:
            print(f"❌ Competition report error: {e}")

    def _generate_mobile_session_report(self, cursor, session_id: str, session_type: str, 
                                      session_date: str, total_drivers: int, best_lap_overall: Optional[int]):
        """Report sessione mobile"""
        try:
            # Format data
            try:
                date_obj = datetime.fromisoformat(session_date.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%d/%m %H:%M')
            except:
                date_str = session_date[:16] if session_date else 'N/A'
            
            print()
            self.print_separator("-")
            print(f"🏁 {session_type} - {date_str}")
            print(f"👥 {total_drivers} drivers")
            self.print_separator("-")
            
            # MODIFICA: Risultati sessione con ordinamento CORRETTO
            # NULL positions vanno in fondo, non in testa
            cursor.execute('''
                SELECT sr.position, sr.race_number, d.last_name, d.short_name,
                       sr.lap_count, sr.best_lap, sr.total_time
                FROM session_results sr
                JOIN drivers d ON sr.driver_id = d.driver_id
                WHERE sr.session_id = ?
                ORDER BY 
                    CASE 
                        WHEN sr.position IS NULL THEN 1 
                        ELSE 0 
                    END,
                    sr.position ASC
                LIMIT 15
            ''', (session_id,))
            
            results = cursor.fetchall()
            
            if not results:
                print("❌ No results found")
                return
            
            # Miglior giro sessione
            session_best_lap = None
            if best_lap_overall:
                session_best_lap = best_lap_overall
            else:
                cursor.execute('''
                    SELECT MIN(lap_time) 
                    FROM laps 
                    WHERE session_id = ? AND is_valid_for_best = 1 AND lap_time > 0
                ''', (session_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    session_best_lap = result[0]
            
            # Top 15 risultati
            for position, race_number, last_name, short_name, lap_count, best_lap, total_time in results[:15]:
                name_display = self.truncate_text(last_name, 22)
                
                # Fix per position = null
                if position is None:
                    pos_str = "NC"  # Non Classificato
                elif position == 1:
                    pos_str = "🥇"
                elif position == 2:
                    pos_str = "🥈"
                elif position == 3:
                    pos_str = "🥉"
                else:
                    pos_str = f"{position:2d}"
                
                # Miglior giro
                if best_lap and best_lap > 0 and best_lap < 10000000:
                    best_lap_str = self.format_lap_time(best_lap)
                else:
                    best_lap_str = "N/A"
                
                # Numero gara
                race_num_str = f"#{race_number:03d}" if race_number else "#000"
                
                # Note per best lap
                notes = ""
                if best_lap and session_best_lap and best_lap == session_best_lap:
                    notes = " ⚡"
                
                # Aggiunto spazio come nella sezione penalità
                print(f"{pos_str} {name_display}")
                print(f"    {race_num_str} | ⏱️ {best_lap_str}{notes}")
                print(f"    🔄 {lap_count if lap_count else 0} laps")
                print()
            
            # Mostra miglior giro se disponibile
            if session_best_lap:
                print(f"⚡ Session best: {self.format_lap_time(session_best_lap)}")
            
        except Exception as e:
            print(f"❌ Session report error: {e}")

    def _generate_mobile_competition_points_report(self, cursor, competition_id: int):
        """Report punti competizione mobile - Formato tabulare con colonne"""
        try:
            cursor.execute('''
                SELECT cr.driver_id, d.last_name, cr.total_points
                FROM competition_results cr
                JOIN drivers d ON cr.driver_id = d.driver_id
                WHERE cr.competition_id = ? AND cr.total_points > 0
                ORDER BY cr.total_points DESC
            ''', (competition_id,))
            
            points_results = cursor.fetchall()
            
            if not points_results:
                print(f"\n✅ NO POINTS AWARDED YET")
                return
            
            print(f"\n🏆 POINTS STANDINGS ({len(points_results)})")
            self.print_separator()
            
            # Header con posizioni fisse - allineato alle colonne dei dati
            print("pos  pilota                     punti\n")
            
            for i, (driver_id, last_name, total_pts) in enumerate(points_results, 1):
                # Gestione separata primi 3 vs resto per allineamento
                if i <= 3:
                    # Prime 3 posizioni con medaglie - spazio fisso di 5 caratteri
                    if i == 1:
                        pos_display = "🥇   "  # medaglia + 3 spazi
                    elif i == 2:
                        pos_display = "🥈   "  # medaglia + 3 spazi  
                    else:  # i == 3
                        pos_display = "🥉   "  # medaglia + 3 spazi
                else:
                    # Posizioni 4+ con numerazione - spazio fisso di 5 caratteri
                    pos_display = f"{i:2d}.  "  # numero + punto + spazio, totale 4 caratteri + 1 spazio = 5
                
                # Nome pilota con larghezza fissa (25 caratteri)
                name_display = self.truncate_text(last_name, 25)
                name_padded = f"{name_display:<25}"
                
                # Punti allineati a destra
                points_str = f"{total_pts:>5}"
                
                # Riga formattata - pos_display è già di 5 caratteri fissi
                print(f"{pos_display}{name_padded} {points_str}")
            
        except Exception as e:
            print(f"❌ Points report error: {e}")

    def _generate_mobile_penalties_report(self, cursor, competition_id: int):
        """Report penalità mobile"""
        try:
            cursor.execute('''
                SELECT p.session_id, s.session_type, d.last_name, d.short_name,
                       p.reason, p.penalty_type, p.penalty_value, p.violation_lap,
                       p.is_post_race
                FROM penalties p
                JOIN sessions s ON p.session_id = s.session_id
                JOIN drivers d ON p.driver_id = d.driver_id
                WHERE s.competition_id = ?
                ORDER BY s.session_order, s.session_date, p.violation_lap
            ''', (competition_id,))
            
            penalties = cursor.fetchall()
            
            if not penalties:
                print(f"\n✅ NO PENALTIES")
                return
            
            print(f"\n🚨 PENALTIES ({len(penalties)})")
            self.print_separator()
            
            current_session = None
            
            for penalty in penalties:
                session_id, session_type, last_name, short_name, reason, penalty_type, penalty_value, violation_lap, is_post_race = penalty
                
                # Header nuova sessione
                if current_session != session_id:
                    current_session = session_id
                    if penalty != penalties[0]:
                        print()
                    print(f"🏁 {session_type}:")
                    print("-" * 25)
                
                name_display = self.truncate_text(last_name, 20)
                reason_display = self.truncate_text(reason, 25)
                
                # Tipo penalità
                if penalty_value and penalty_value > 0:
                    penalty_display = f"{penalty_type} {penalty_value}s"
                else:
                    penalty_display = penalty_type
                penalty_display = self.truncate_text(penalty_display, 20)
                
                # Info giro e timing
                lap_info = f"L{violation_lap}" if violation_lap else "N/A"
                timing = "Post-race" if is_post_race else "In-race"
                
                print(f"👤 {name_display}")
                print(f"    📝 {reason_display}")
                print(f"    🚨 {penalty_display}")
                print(f"    🔄 {lap_info} ({timing})")
                print()
            
        except Exception as e:
            print(f"❌ Penalties report error: {e}")

    # === 2. OVERVIEW PISTE ===
    
    def show_mobile_tracks_overview(self):
        """Overview tutte le piste mobile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
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
            
            self.print_header("🏁 ALL TRACKS OVERVIEW")
            
            for track, sessions, drivers, record in tracks:
                track_display = self.truncate_text(track, 32)
                record_str = self.format_lap_time(record) if record else "N/A"
                
                print(f"\n🏁 {track_display}")
                print(f"📊 {sessions} sessions | {drivers} drivers")
                print(f"⚡ Record: {record_str}")
                
                # Record holder
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
                    if record_holder:
                        holder_display = self.truncate_text(record_holder[0], 25)
                        print(f"👤 {holder_display}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Overview error: {e}")

    # === 6. REPORT CAMPIONATI ===

    def show_mobile_championship_report(self):
        """Report campionato dettagliato per mobile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            self.print_header("🏆 CHAMPIONSHIP REPORT")
            
            print("\n📋 SELECTION METHOD:")
            print("  1. Enter championship ID")
            print("  2. Choose from completed list")
            print("  0. Return to menu")
            
            selection_method = input("\nChoice: ").strip()
            
            if selection_method == "0":
                conn.close()
                return
            elif selection_method == "1":
                championship_id = self._select_championship_by_id_mobile(cursor)
            elif selection_method == "2":
                championship_id = self._select_championship_from_list_mobile(cursor)
            else:
                print("❌ Invalid choice")
                conn.close()
                return
            
            if not championship_id:
                conn.close()
                return
            
            # Genera report campionato
            self._generate_mobile_championship_report(cursor, championship_id)
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Championship report error: {e}")

    def _select_championship_by_id_mobile(self, cursor) -> Optional[int]:
        """Selezione campionato per ID mobile"""
        try:
            champ_id_input = input("\n🔍 Enter championship ID: ").strip()
            
            if not champ_id_input.isdigit():
                print("❌ Invalid ID")
                return None
            
            championship_id = int(champ_id_input)
            
            cursor.execute('''
                SELECT championship_id, name, season, start_date, end_date, is_completed
                FROM championships
                WHERE championship_id = ?
            ''', (championship_id,))
            
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Championship {championship_id} not found")
                return None
            
            champ_id, name, season, start_date, end_date, is_completed = result
            
            name_display = self.truncate_text(name, 30)
            status = "✅ Completed" if is_completed else "🔄 In progress"
            
            print(f"\n📋 CHAMPIONSHIP FOUND")
            self.print_separator()
            print(f"📛 {name_display}")
            print(f"📅 Season: {season}")
            if start_date and end_date:
                print(f"🗓️  {start_date[:10]} - {end_date[:10]}")
            print(f"📊 {status}")
            
            confirm = input("\n❓ Proceed? (y/N): ").strip().lower()
            if confirm in ['s', 'si', 'sì', 'y', 'yes']:
                return championship_id
            
            return None
            
        except Exception as e:
            print(f"❌ ID selection error: {e}")
            return None

    def _select_championship_from_list_mobile(self, cursor) -> Optional[int]:
        """Selezione campionato da lista mobile"""
        try:
            cursor.execute('''
                SELECT ch.championship_id, ch.name, ch.season, ch.start_date, ch.end_date,
                       COUNT(c.competition_id) as total_competitions
                FROM championships ch
                LEFT JOIN competitions c ON ch.championship_id = c.championship_id
                WHERE ch.is_completed = 1
                GROUP BY ch.championship_id
                ORDER BY ch.season DESC, ch.name
                LIMIT 20
            ''')
            
            completed_championships = cursor.fetchall()
            
            if not completed_championships:
                print("\n❌ No completed championships found")
                return None
            
            self.print_header(f"🏆 COMPLETED ({len(completed_championships)})")
            
            for i, (champ_id, name, season, start_date, end_date, total_comps) in enumerate(completed_championships, 1):
                name_display = self.truncate_text(name, 25)
                season_str = f"({season})" if season else ""
                
                print(f"{i:2d}. {name_display} {season_str}")
                
                if start_date and end_date:
                    print(f"    📅 {start_date[:10]} - {end_date[:10]}")
                
                print(f"    🏁 {total_comps} competitions")
                print()
            
            try:
                choice = input(f"Choose (1-{len(completed_championships)}): ").strip()
                choice_int = int(choice) - 1
                
                if 0 <= choice_int < len(completed_championships):
                    return completed_championships[choice_int][0]
                else:
                    print("❌ Invalid choice")
                    return None
                    
            except ValueError:
                print("❌ Invalid input")
                return None
                
        except Exception as e:
            print(f"❌ List selection error: {e}")
            return None

    def _generate_mobile_championship_report(self, cursor, championship_id: int):
        """Genera report campionato mobile"""
        try:
            # Info campionato
            cursor.execute('''
                SELECT championship_id, name, season, start_date, end_date, 
                       description, is_completed
                FROM championships
                WHERE championship_id = ?
            ''', (championship_id,))
            
            champ_info = cursor.fetchone()
            if not champ_info:
                print("❌ Championship not found")
                return
            
            champ_id, name, season, start_date, end_date, description, is_completed = champ_info
            
            # Header campionato
            name_display = self.truncate_text(name, 36)
            #season_str = f" ({season})" if season else ""
            season_str = ""
            self.print_header(f"🏆 {name_display}{season_str}")
            
            print("\n📋 CHAMPIONSHIP INFO")
            self.print_separator()
            print(f"🆔 ID: {champ_id}")
            
            if start_date and end_date:
                print(f"📅 {start_date[:10]} - {end_date[:10]}")
            
            if description:
                desc_display = self.truncate_text(description, 35)
                print(f"📝 {desc_display}")
            
            status = "✅ Completed" if is_completed else "🔄 In progress"
            print(f"📊 {status}")
            
            # Riepilogo competizioni
            self._generate_mobile_championship_competitions_summary(cursor, championship_id)
            
            # Classifica campionato
            self._generate_mobile_championship_standings(cursor, championship_id)
            
        except Exception as e:
            print(f"❌ Championship report error: {e}")

    def _generate_mobile_championship_competitions_summary(self, cursor, championship_id: int):
        """Riepilogo competizioni del campionato mobile"""
        try:
            cursor.execute('''
                SELECT c.competition_id, c.name, c.track_name, c.date_start, 
                       c.weekend_format, c.round_number, c.is_completed
                FROM competitions c
                WHERE c.championship_id = ?
                ORDER BY c.round_number, c.date_start, c.name
            ''', (championship_id,))
            
            competitions = cursor.fetchall()
            
            if not competitions:
                print(f"\n❌ No competitions found")
                return
            
            print(f"\n🏁 COMPETITIONS ({len(competitions)})")
            self.print_separator()
            
            for comp_id, comp_name, track, date_start, weekend_format, round_num, is_completed in competitions:
                # Round number
                round_str = f"R{round_num}" if round_num else "R?"
                
                # Data inizio
                if date_start:
                    date_str = date_start[:10]  # YYYY-MM-DD
                else:
                    date_str = "N/A"
                
                # Nome competizione
                comp_display = self.truncate_text(comp_name, 25)
                
                # Pista
                track_display = self.truncate_text(track, 20)
                
                # Weekend format
                if weekend_format:
                    format_display = self.truncate_text(weekend_format, 15)
                else:
                    format_display = "N/A"
                
                # Status
                status = "✅" if is_completed else "🔄"
                
                print(f"{round_str} - {date_str} {status}")
                print(f"    📛 {comp_display}")
                print(f"    🏁 {track_display}")
                print(f"    📋 {format_display}")
                print()
            
        except Exception as e:
            print(f"❌ Competitions summary error: {e}")

    def _generate_mobile_championship_standings(self, cursor, championship_id: int):
        """Classifica campionato mobile"""
        try:
            cursor.execute('''
                SELECT chs.driver_id, d.last_name, chs.total_points, chs.position,
                       chs.wins
                FROM championship_standings chs
                JOIN drivers d ON chs.driver_id = d.driver_id
                WHERE chs.championship_id = ?
                GROUP BY chs.driver_id
                ORDER BY chs.position ASC, chs.total_points DESC
            ''', (championship_id,))
            
            standings = cursor.fetchall()
            
            if not standings:
                print(f"\n❌ No championship standings found")
                return
            
            print(f"\n🏆 CHAMPIONSHIP STANDINGS")
            self.print_separator()
            
            # Header con posizioni fisse
            print("pos  driver               points  wins\n")
            
            for driver_id, last_name, total_points, position, wins in standings:
                # Posizione con medaglie per primi 3
                if position == 1:
                    pos_display = "🥇   "
                elif position == 2:
                    pos_display = "🥈   "
                elif position == 3:
                    pos_display = "🥉   "
                else:
                    pos_display = f"{position:2d}.  "
                
                # Nome pilota con larghezza fissa
                name_display = self.truncate_text(last_name, 20)
                name_padded = f"{name_display:<20}"
                
                # Punti e vittorie allineati
                points_str = f"{total_points:>5}"
                wins_str = f"{wins:>4}"
                
                print(f"{pos_display}{name_padded} {points_str} {wins_str}")
            
        except Exception as e:
            print(f"❌ Championship standings error: {e}")

    # === MENU PRINCIPALE ===
    
    def show_mobile_menu(self):
        """Menu principale mobile"""
        while True:
            community_name = self.config['community']['name']
            short_name = self.truncate_text(community_name, 20)
            
            self.print_header(f"📱 {short_name} MOBILE")
            
            print("\n📋 REPORTS MENU:")
            print("  1. General statistics")
            print("  2. All tracks overview")
            print("  3. Single Track report")
            print("  4. Detailed driver report")
            print("  5. Competition report")
            print("  6. Championship report")
            print("  0. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                self.show_mobile_general_statistics()
            elif choice == "2":
                self.show_mobile_tracks_overview()
            elif choice == "3":
                self.show_mobile_track_report()
            elif choice == "4":
                self.show_mobile_driver_report()
            elif choice == "5":
                self.show_mobile_advanced_competition_report()
            elif choice == "6":
                self.show_mobile_championship_report()
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
        print("📱 ACC Mobile Reporter Suite")
        print("Optimized for smartphone displays")
        print("Max 38-40 characters per line\n")
        
        reporter = ACCMobileReporter()
        reporter.show_mobile_menu()
        
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")

if __name__ == "__main__":
    main()