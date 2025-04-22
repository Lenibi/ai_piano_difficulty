import json
import argparse
from midiutil import MIDIFile

# Default resolution if not found in JSON (should match standard MIDI)
DEFAULT_RESOLUTION = 480

def json_to_midi(json_filepath, midi_filepath):
    """
    Converts a JSON file containing note data (in beats) and a tempo map
    into a MIDI file.

    The JSON file should be an object containing:
    - "resolution": Ticks per quarter note (PPQN) - Optional, defaults to 480.
    - "tempo_map": List of tempo changes [{"beat": float_beat, "bpm": float_bpm}].
    - "notes": A list of objects, where each object represents a note and has:
        - "pitch": MIDI note number (0-127)
        - "start_beat": Start time of the note in beats.
        - "duration_beat": Duration of the note in beats.
        - "velocity": MIDI velocity (0-127, optional, defaults to 100).
        - "track": MIDI track number (optional, defaults to 0).
        - "channel": MIDI channel number (0-15, optional, defaults to 0).

    Args:
        json_filepath (str): Path to the input JSON file.
        midi_filepath (str): Path to the output MIDI file.
    """
    try:
        with open(json_filepath, 'r') as f:
            input_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input JSON file not found at '{json_filepath}'")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{json_filepath}'")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading the JSON file: {e}")
        return

    # --- Extract data from JSON ---
    if not isinstance(input_data, dict) or 'notes' not in input_data or 'tempo_map' not in input_data:
         print("Error: JSON data must be an object with 'notes' and 'tempo_map' keys.")
         return

    notes_data = input_data['notes']
    tempo_map = input_data['tempo_map']
    resolution = input_data.get('resolution', DEFAULT_RESOLUTION) # Ticks per quarter note

    if not isinstance(notes_data, list):
        print("Error: 'notes' key in JSON does not contain a list.")
        return
    if not isinstance(tempo_map, list) or not tempo_map:
         print("Error: 'tempo_map' key in JSON must contain a non-empty list.")
         # Optionally add a default tempo if you want to be lenient
         # tempo_map = [{"beat": 0.0, "bpm": 120.0}]
         return
    # --- End Data Extraction ---


    # Determine the number of tracks needed from the JSON data
    tracks = set(note.get('track', 0) for note in notes_data if isinstance(note, dict))
    num_tracks = max(tracks) + 1 if tracks else 1
    print(f"Detected {num_tracks} tracks based on note data.")

    # Create the MIDIFile object
    # midiutil uses resolution (ticks per beat) in adjustResolution
    midi_file = MIDIFile(numTracks=num_tracks, ticks_per_quarternote=resolution)


    # Apply tempo map to all tracks
    # midiutil applies tempo changes across all tracks implicitly if added to track 0,
    # but let's add explicitly to be sure and consistent.
    tempo_added_tracks = set()
    for track_num in range(num_tracks):
        midi_file.addTrackName(track_num, 0, f"Track {track_num}")
        # Add all tempo changes from the map
        for tempo_event in tempo_map:
            beat = tempo_event.get('beat', 0.0)
            bpm = tempo_event.get('bpm', 120.0)
            # Ensure beat is non-negative
            if beat < 0:
                print(f"Warning: Tempo event has negative beat time ({beat}), setting to 0.")
                beat = 0.0
            midi_file.addTempo(track_num, beat, bpm)
            # No need for tempo_added_tracks set anymore as we add all events


    # Add notes to the MIDI file
    note_count = 0
    skipped_count = 0

    for note in notes_data:
        if not isinstance(note, dict):
            print(f"Warning: Skipping invalid entry (not a dictionary): {note}")
            skipped_count += 1
            continue

        try:
            # Required fields (now in beats)
            pitch = int(note['pitch'])
            start_beat = float(note['start_beat'])
            duration_beat = float(note['duration_beat'])

            # Optional fields with defaults
            track = int(note.get('track', 0))
            channel = int(note.get('channel', 0))
            velocity = int(note.get('velocity', 100)) # Default velocity

            # --- Basic Validation ---
            if not (0 <= pitch <= 127):
                 raise ValueError("Pitch out of range (0-127)")
            if not (0 <= velocity <= 127):
                 raise ValueError("Velocity out of range (0-127)")
            if not (0 <= channel <= 15):
                 raise ValueError("Channel out of range (0-15)")
            if track < 0 or track >= num_tracks:
                 # If track number from JSON exceeds calculated max, print warning but proceed
                 print(f"Warning: Note specifies track {track}, which is >= calculated max tracks {num_tracks}. Adding to track {track}, ensure MIDI player supports it.")
                 # Or clamp it: track = max(0, min(track, num_tracks - 1))
                 # Or raise error: raise ValueError(...)
            if start_beat < 0 or duration_beat <= 0:
                 raise ValueError("Start beat must be non-negative and duration beat must be positive")


            # Add the note (using times in beats)
            midi_file.addNote(track, channel, pitch, start_beat, duration_beat, velocity)
            note_count += 1

        except KeyError as e:
            print(f"Warning: Skipping note due to missing required key: {e}. Note data: {note}")
            skipped_count += 1
        except (TypeError, ValueError) as e:
            print(f"Warning: Skipping invalid note: {e}. Note data: {note}")
            skipped_count += 1
        except Exception as e:
            print(f"Warning: Skipping note due to unexpected error: {e}. Note data: {note}")
            skipped_count += 1


    # Write the MIDI file
    try:
        with open(midi_filepath, "wb") as output_file:
            midi_file.writeFile(output_file)
        print(f"\nSuccessfully created MIDI file: '{midi_filepath}'")
        print(f"Processed {note_count} notes.")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} invalid entries.")
    except IOError:
        print(f"Error: Could not write MIDI file to '{midi_filepath}'")
    except Exception as e:
        print(f"An unexpected error occurred while writing the MIDI file: {e}")


if __name__ == "__main__":
    # Remove the --tempo argument as it's now handled by the tempo map in JSON
    parser = argparse.ArgumentParser(description="Convert a JSON file (with notes in beats and tempo map) to a MIDI file.")
    parser.add_argument("json_file", help="Path to the input JSON file.")
    parser.add_argument("midi_file", help="Path to the output MIDI file (e.g., output.mid).")
    # parser.add_argument("-t", "--tempo", type=float, default=None, ...) # REMOVED

    args = parser.parse_args()

    json_to_midi(args.json_file, args.midi_file) # Pass only json and midi paths