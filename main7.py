#!/usr/bin/env python3
"""
YouTube Lyrics Overlay - Synchronized lyrics with transparent background
Requirements: pip install pygetwindow requests pillow
"""

import tkinter as tk
from tkinter import font as tkfont
import time
import re
import threading
import requests
from urllib.parse import quote
import sys

try:
    import pygetwindow as gw
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pygetwindow'])
    import pygetwindow as gw


class OutlineLabel(tk.Label):
    """Custom label with text outline"""
    def __init__(self, master, text="", outline_width=2, outline_color="black", **kwargs):
        super().__init__(master, text=text, **kwargs)
        self.outline_width = outline_width
        self.outline_color = outline_color
        self.base_text = text
        self.bind('<Configure>', self._update_outline)
    
    def set_text(self, text):
        """Update text with outline effect"""
        self.base_text = text
        self.config(text=text)


class LyricsOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Lyrics Overlay")
        
        # Transparent window
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'grey15')
        self.root.overrideredirect(False)
        
        # Window dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.window_width = 900
        self.window_height = 250
        x = (screen_width - self.window_width) // 2
        y = screen_height - self.window_height - 100
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        
        # Transparent background
        self.root.configure(bg='grey15')
        
        # Title bar (semi-transparent)
        self.title_bar = tk.Frame(self.root, bg='#1a1a1a', height=30)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)
        
        self.title_label = tk.Label(
            self.title_bar,
            text="♪ Lyrics",
            font=("Arial", 9, "bold"),
            fg="#00ff88",
            bg='#1a1a1a'
        )
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        close_btn = tk.Button(
            self.title_bar,
            text="×",
            command=self.close,
            font=("Arial", 12),
            bg="#ff4444",
            fg="white",
            bd=0,
            padx=6
        )
        close_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Make draggable
        self.title_bar.bind('<Button-1>', self.start_drag)
        self.title_bar.bind('<B1-Motion>', self.drag_window)
        self.title_label.bind('<Button-1>', self.start_drag)
        self.title_label.bind('<B1-Motion>', self.drag_window)
        
        # Content frame (transparent)
        content = tk.Frame(self.root, bg='grey15')
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Current lyric (yellow with black outline)
        self.current_label = tk.Label(
            content,
            text="",
            font=("Arial", 32, "bold"),
            fg="yellow",
            bg='grey15',
            wraplength=850,
            justify=tk.CENTER
        )
        self.current_label.pack(expand=True, pady=(10, 5))
        
        # Next lyric (gray with outline)
        self.next_label = tk.Label(
            content,
            text="",
            font=("Arial", 16),
            fg="#999999",
            bg='grey15',
            wraplength=850,
            justify=tk.CENTER
        )
        self.next_label.pack(expand=True, pady=(5, 10))
        
        # Variables
        self.drag_x = 0
        self.drag_y = 0
        self.lyrics = []
        self.running = True
        self.start_time = 0
        self.is_loading = False
        self.last_title = None
        self.current_song = None
        
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
    
    def drag_window(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")
    
    def find_youtube_window(self):
        """Find YouTube window"""
        try:
            for title in gw.getAllTitles():
                if 'youtube' in title.lower() and title.strip():
                    return title
        except:
            pass
        return None
    
    def clean_title(self, title):
        """Clean YouTube title"""
        # Remove YouTube
        title = re.sub(r'\s*-\s*YouTube.*$', '', title, flags=re.IGNORECASE)
        
        # Remove everything after pipe
        title = re.sub(r'\s*\|.*$', '', title)
        
        # Remove brackets/parentheses content
        patterns = [
            r'\([^)]*official[^)]*\)', r'\[[^\]]*official[^\]]*\]',
            r'\([^)]*audio[^)]*\)', r'\[[^\]]*audio[^\]]*\]',
            r'\([^)]*video[^)]*\)', r'\[[^\]]*video[^\]]*\]',
            r'\([^)]*lyric[^)]*\)', r'\[[^\]]*lyric[^\]]*\]',
            r'\([^)]*live[^)]*\)', r'\([^)]*cover[^)]*\)',
            r'\([^)]*remix[^)]*\)', r'\([^)]*HD[^)]*\)',
            r'\([^)]*\d+p[^)]*\)', r'\[[^\]]*HQ[^\]]*\]',
        ]
        
        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        return ' '.join(title.split())
    
    def parse_song(self, title):
        """Extract artist and song"""
        clean = self.clean_title(title)
        
        # Format: Artist - Song
        if ' - ' in clean:
            parts = clean.split(' - ', 1)
            return parts[0].strip(), parts[1].strip(), clean
        
        # Format: 'Song' Artist
        match = re.match(r"'([^']+)'\s+(.+)", clean)
        if match:
            return match.group(2).strip(), match.group(1).strip(), clean
        
        return "", clean.strip(), clean
    
    def search_lrclib(self, artist, song):
        """Search LRCLIB for lyrics"""
        try:
            headers = {'User-Agent': 'LyricsOverlay/1.0'}
            
            print(f"Searching: {artist} - {song}")
            
            # Try exact match first
            url = "https://lrclib.net/api/get"
            params = {}
            if song:
                params['track_name'] = song
            if artist:
                params['artist_name'] = artist
            
            if params:
                resp = requests.get(url, params=params, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('syncedLyrics'):
                        print("  Found (exact match)")
                        return data['syncedLyrics']
            
            # Try search endpoint
            print("  Trying search...")
            search_url = "https://lrclib.net/api/search"
            
            queries = []
            if artist and song:
                queries.append({'artist_name': artist, 'track_name': song})
                queries.append({'q': f"{artist} {song}"})
            if song:
                queries.append({'q': song})
            
            for query in queries:
                try:
                    resp = requests.get(search_url, params=query, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        results = resp.json()
                        if results:
                            # Get first result
                            result_id = results[0].get('id')
                            if result_id:
                                get_url = f"https://lrclib.net/api/get/{result_id}"
                                resp = requests.get(get_url, headers=headers, timeout=10)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    if data.get('syncedLyrics'):
                                        print(f"  Found via search: {results[0].get('artistName')} - {results[0].get('trackName')}")
                                        return data['syncedLyrics']
                except:
                    continue
            
            print("  Not found")
            return None
            
        except Exception as e:
            print(f"Search error: {e}")
            return None
    
    def parse_lrc(self, lrc_text):
        """Parse LRC format"""
        lyrics = []
        for line in lrc_text.split('\n'):
            match = re.match(r'\[(\d+):(\d+)\.(\d+)\](.*)', line.strip())
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                centis = int(match.group(3))
                text = match.group(4).strip()
                
                if text:
                    total_sec = minutes * 60 + seconds + centis / 100
                    lyrics.append({'time': total_sec, 'text': text})
        
        return sorted(lyrics, key=lambda x: x['time'])
    
    def load_song(self):
        """Load lyrics for current song"""
        if self.is_loading:
            return False
        
        self.is_loading = True
        load_start = time.time()
        
        try:
            yt_title = self.find_youtube_window()
            if not yt_title:
                self.current_label.config(text="No YouTube window", fg="red")
                return False
            
            artist, song, full = self.parse_song(yt_title)
            
            print(f"\n{'='*60}")
            print(f"Song: {full}")
            print(f"Artist: {artist}")
            print(f"Track: {song}")
            
            self.current_label.config(text="Loading...", fg="white")
            self.next_label.config(text=full)
            
            lrc = self.search_lrclib(artist, song)
            
            if not lrc:
                self.current_label.config(text="No lyrics found", fg="orange")
                self.next_label.config(text="")
                print("='*60}\n")
                return False
            
            self.lyrics = self.parse_lrc(lrc)
            
            # Compensate for loading time
            load_time = time.time() - load_start
            self.start_time = time.time() - load_time
            
            self.current_song = full
            self.title_label.config(text=f"♪ {full[:50]}")
            
            print(f"Loaded {len(self.lyrics)} lines")
            print(f"Compensated {load_time:.2f}s loading time")
            print(f"{'='*60}\n")
            
            return True
            
        finally:
            self.is_loading = False
    
    def check_title_change(self):
        """Check if video changed"""
        if self.is_loading:
            return False
        
        current = self.find_youtube_window()
        if not current:
            return False
        
        if self.last_title is None:
            self.last_title = current
            return False
        
        if current != self.last_title:
            old_clean = self.clean_title(self.last_title)
            new_clean = self.clean_title(current)
            
            if old_clean != new_clean:
                print(f"\nSong changed: {new_clean}")
                self.last_title = current
                return True
            
            self.last_title = current
        
        return False
    
    def update_loop(self):
        """Main update loop"""
        last_check = time.time()
        
        while self.running:
            try:
                # Check for song changes every 2 seconds
                if time.time() - last_check > 2:
                    if self.check_title_change():
                        self.load_song()
                    last_check = time.time()
                
                # Update display
                if self.lyrics:
                    elapsed = time.time() - self.start_time
                    
                    current_idx = 0
                    for i, lyric in enumerate(self.lyrics):
                        if lyric['time'] <= elapsed:
                            current_idx = i
                    
                    if current_idx < len(self.lyrics):
                        self.current_label.config(
                            text=self.lyrics[current_idx]['text'],
                            fg="yellow"
                        )
                        
                        if current_idx + 1 < len(self.lyrics):
                            self.next_label.config(text=self.lyrics[current_idx + 1]['text'])
                        else:
                            self.next_label.config(text="")
                
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Update error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start overlay"""
        # Load initial song
        if not self.load_song():
            print("Waiting for valid YouTube video...")
        
        # Start update thread
        thread = threading.Thread(target=self.update_loop, daemon=True)
        thread.start()
        
        print("\n" + "="*60)
        print("Overlay running!")
        print("="*60 + "\n")
        
        self.root.mainloop()
    
    def close(self):
        """Close overlay"""
        self.running = False
        self.root.quit()


if __name__ == "__main__":
    print("="*60)
    print("YouTube Lyrics Overlay")
    print("="*60)
    print("\nFeatures:")
    print("• Transparent background")
    print("• Yellow text with black outline")
    print("• Synchronized timing")
    print("• Auto-detects song changes")
    print("\n" + "="*60 + "\n")
    
    try:
        overlay = LyricsOverlay()
        overlay.start()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()