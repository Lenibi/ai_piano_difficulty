import json
import math

# Load the original Ballade JSON
with open('/mnt/data/ballade_no_1.json') as f:
    data = json.load(f)

resolution = data.get('resolution', 480)
tempo_map = data.get('tempo_map', [{"beat": 0.0, "bpm": 120.0}])
notes = data.get('notes', [])

new_notes = []
for note in notes:
    new_notes.append(note)
    start = note['start_beat']
    dur = note['duration_beat']
    vel = note['velocity']
    track = note.get('track', 0)
    
    # Insane fast repeated notes
    for i in range(1, 5):
        new_notes.append({
            'pitch': note['pitch'],
            'start_beat': start + i * dur / 6,
            'duration_beat': dur / 12,
            'velocity': vel,
            'track': track
        })
    
    # Insane arpeggio chords (major triad)
    triad = [note['pitch'] + 4, note['pitch'] + 7]
    for idx, p in enumerate(triad):
        ar_start = start + idx * (dur / 4)
        new_notes.append({
            'pitch': p,
            'start_beat': ar_start,
            'duration_beat': dur / 8,
            'velocity': vel,
            'track': track
        })
    
    # Wide leaps (octave leap)
    new_notes.append({
        'pitch': note['pitch'] + 12,
        'start_beat': start + dur / 2,
        'duration_beat': dur / 8,
        'velocity': vel,
        'track': track
    })

# Polyrhythmic overlay: triplets across each whole beat
max_beat = max(n['start_beat'] + n['duration_beat'] for n in notes)
for b in range(int(math.ceil(max_beat))):
    for i in range(3):
        new_notes.append({
            'pitch': 60 + (b % 12),
            'start_beat': b + i / 3,
            'duration_beat': 1 / 3,
            'velocity': 70,
            'track': 1
        })

# Sort notes by start time
new_notes.sort(key=lambda x: x['start_beat'])

# Prepare final JSON
output = {
    'resolution': resolution,
    'tempo_map': tempo_map,
    'notes': new_notes
}

# Write to file
file_path = '/mnt/data/insane_ballade.json'
with open(file_path, 'w') as out:
    json.dump(output, out, indent=2)

print(f"Saved to {file_path}")
