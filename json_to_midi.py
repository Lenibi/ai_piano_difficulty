import json
import argparse
import pretty_midi
import math # For infinity

# Default resolution if not found in JSON (PPQN) - pretty_midi uses ticks per beat internally
DEFAULT_RESOLUTION = 480

def get_time_from_beat(target_beat, beat_time_map, tempo_map_dict):
    """Converts a beat number to time in seconds based on the tempo map."""
    if not beat_time_map:
        # Fallback to a default tempo if beat_time_map is somehow empty
        bpm = 120.0
        print("Warning: beat_time_map is empty, using default 120 BPM for conversion.")
        return (target_beat * 60.0) / bpm

    # Find the segment in beat_time_map that contains target_beat
    map_idx = -1
    for i in range(len(beat_time_map) - 1):
        if beat_time_map[i][0] <= target_beat < beat_time_map[i+1][0]:
            map_idx = i
            break
    else:
        # If target_beat is beyond the last map point, use the last segment
        map_idx = len(beat_time_map) - 1

    seg_start_beat, seg_start_time = beat_time_map[map_idx]

    # Find the BPM active at the start of this segment
    # Use the tempo_map_dict which stores beat -> bpm mapping
    active_bpm = tempo_map_dict.get(seg_start_beat, 120.0) # Default to 120 if somehow not found

    # Calculate the beat offset within the segment
    beat_offset = target_beat - seg_start_beat

    # Calculate the time offset in seconds for this segment
    time_offset_sec = 0
    if active_bpm > 0: # Avoid division by zero
        time_offset_sec = (beat_offset * 60.0) / active_bpm
    else:
         print(f"Warning: Encountered zero or negative BPM ({active_bpm}) at beat {seg_start_beat}. Time calculation might be incorrect.")


    return seg_start_time + time_offset_sec


def json_to_midi(json_filepath, midi_filepath):
    """
    Converts a JSON file containing note data (in beats) and a tempo map
    into a MIDI file using the pretty_midi library.

    Handles beat-to-time conversion based on the tempo map.
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
    # pretty_midi doesn't explicitly use resolution in object creation, but it's important for internal ticks
    # resolution = input_data.get('resolution', DEFAULT_RESOLUTION)

    if not isinstance(notes_data, list):
        print("Error: 'notes' key in JSON does not contain a list.")
        return
    if not isinstance(tempo_map, list) or not tempo_map:
        print("Error: 'tempo_map' key in JSON must contain a non-empty list.")
        # Add a default tempo if needed
        tempo_map = [{"beat": 0.0, "bpm": 120.0}]
        print("Warning: Tempo map was empty, adding default 120 BPM at beat 0.")
    # --- End Data Extraction ---

    # --- Prepare Beat-to-Time Conversion ---
    try:
        # Ensure all tempo events are dicts and sort by beat
        if not all(isinstance(event, dict) for event in tempo_map):
            raise TypeError("Tempo map contains non-dictionary elements.")
        tempo_map.sort(key=lambda x: float(x.get('beat', 0.0)))

        # Ensure tempo map starts at beat 0
        if tempo_map[0].get('beat', 0.0) > 0.0:
            default_start_tempo = 120.0
            print(f"Warning: No tempo event found at beat 0. Inserting default tempo {default_start_tempo} BPM at beat 0.")
            tempo_map.insert(0, {"beat": 0.0, "bpm": default_start_tempo})

    except (TypeError, ValueError, KeyError) as e:
        print(f"Error: Could not process tempo map. Invalid tempo event found: {e}")
        return

    # Build the beat-to-time lookup map and a dictionary for BPM at each change point
    beat_time_map = [(0.0, 0.0)] # List of (beat, time_in_seconds) tuples
    tempo_map_dict = {}        # Dictionary of beat -> bpm
    current_time_sec = 0.0
    last_beat = 0.0
    last_bpm = 120.0 # Default if first event isn't at beat 0 (though we added one)

    for i, event in enumerate(tempo_map):
        try:
            event_beat = float(event.get('beat', 0.0))
            event_bpm = float(event.get('bpm', 120.0))

            if event_beat < last_beat:
                 print(f"Warning: Tempo map not sorted correctly at index {i}, beat {event_beat} < {last_beat}. Skipping event.")
                 continue
            if event_bpm <= 0:
                 print(f"Warning: Tempo event has zero or negative BPM ({event_bpm}) at beat {event_beat}. Using 120 BPM instead for calculation.")
                 event_bpm = 120.0


            if i > 0: # Calculate time elapsed since the last event
                 beat_diff = event_beat - last_beat
                 if last_bpm > 0:
                      time_diff_sec = (beat_diff * 60.0) / last_bpm
                      current_time_sec += time_diff_sec
                 else:
                      # If last bpm was invalid, we can't calculate time diff accurately
                      print(f"Warning: Cannot calculate time difference accurately due to previous invalid BPM.")


            # Add mapping point *only if beat is different from last* to avoid duplicates if multiple events at same beat
            if event_beat > last_beat or i == 0:
                 beat_time_map.append((event_beat, current_time_sec))
                 tempo_map_dict[event_beat] = event_bpm # Store BPM for this beat marker


            last_beat = event_beat
            last_bpm = event_bpm # Update BPM for the *next* segment calculation

        except (TypeError, ValueError) as e:
            print(f"Warning: Skipping invalid tempo event: {event}. Error: {e}")
            continue

    # --- Create PrettyMIDI object ---
    pm = pretty_midi.PrettyMIDI()

    # --- Create Instruments (Tracks) ---
    # Determine unique tracks used in notes
    note_tracks = set(int(note.get('track', 0)) for note in notes_data if isinstance(note, dict) and 'track' in note)
    instruments = {} # Dictionary to hold track_number -> Instrument
    for track_num in sorted(list(note_tracks)):
        if track_num < 0:
            print(f"Warning: Note found with negative track number {track_num}. Skipping.")
            continue
        # You might want to map track numbers to MIDI programs (instruments) here
        # For now, use default program 0 (Acoustic Grand Piano)
        instrument = pretty_midi.Instrument(program=0, is_drum=False, name=f'Track {track_num}')
        instruments[track_num] = instrument
        print(f"Created instrument for track {track_num}")

    # If no tracks were found in notes, create a default track 0
    if not instruments:
         print("No tracks found in notes, creating default instrument for track 0.")
         instrument = pretty_midi.Instrument(program=0, is_drum=False, name='Track 0')
         instruments[0] = instrument


    # --- Add Notes ---
    note_count = 0
    skipped_count = 0
    notes_added_to_track = {track_num: 0 for track_num in instruments}


    for i, note in enumerate(notes_data):
        if not isinstance(note, dict):
            print(f"Warning: Skipping invalid entry (not a dictionary) at index {i}: {note}")
            skipped_count += 1
            continue

        try:
            # Extract data
            pitch = int(note['pitch'])
            start_beat = float(note['start_beat'])
            duration_beat = float(note['duration_beat'])
            velocity = int(note.get('velocity', 100))
            track = int(note.get('track', 0))
            # channel = int(note.get('channel', 0)) # pretty_midi doesn't use channel directly in Note object

            # Basic Validation
            if not (0 <= pitch <= 127): raise ValueError("Pitch out of range (0-127)")
            if not (0 <= velocity <= 127): raise ValueError("Velocity out of range (0-127)")
            if start_beat < 0: raise ValueError("Start beat must be non-negative")
            if duration_beat <= 0: raise ValueError("Duration beat must be positive")
            if track not in instruments:
                 print(f"Warning: Note specifies track {track} but no instrument was created for it (maybe invalid track number?). Skipping note.")
                 skipped_count += 1
                 continue


            # Convert beats to time (seconds)
            start_time = get_time_from_beat(start_beat, beat_time_map, tempo_map_dict)
            end_time = get_time_from_beat(start_beat + duration_beat, beat_time_map, tempo_map_dict)

            # Ensure end time is strictly after start time
            if end_time <= start_time:
                 # This can happen with very short notes and tempo changes, or rounding
                 # Option 1: Skip the note
                 # print(f"Warning: Skipping note with non-positive duration in seconds ({end_time - start_time:.6f}) after time conversion. Note: {note}")
                 # skipped_count += 1
                 # continue
                 # Option 2: Give it a tiny minimum duration in seconds
                 min_duration_sec = 0.001 # Or some other small value
                 end_time = start_time + min_duration_sec
                 print(f"Warning: Note duration became non-positive after time conversion. Setting to {min_duration_sec}s. Note: {note}")



            # Create pretty_midi Note object
            midi_note = pretty_midi.Note(
                velocity=velocity,
                pitch=pitch,
                start=start_time,
                end=end_time
            )

            # Add note to the corresponding instrument
            instruments[track].notes.append(midi_note)
            notes_added_to_track[track] += 1
            note_count += 1

        except KeyError as e:
            print(f"SKIPPING NOTE (KeyError: {e}): {note}")
            skipped_count += 1
        except (TypeError, ValueError) as e:
            print(f"SKIPPING NOTE (TypeError/ValueError: {e}): {note}")
            skipped_count += 1
        except Exception as e:
            print(f"SKIPPING NOTE (Exception: {e}): {note}")
            skipped_count += 1

    # Add instruments to the PrettyMIDI object
    for track_num in sorted(instruments.keys()):
        if notes_added_to_track[track_num] > 0:
             pm.instruments.append(instruments[track_num])
             print(f"Added instrument Track {track_num} with {notes_added_to_track[track_num]} notes to MIDI.")
        else:
             print(f"Skipping empty instrument Track {track_num}.")


    # --- Write the MIDI file ---
    try:
        print(f"Processed {note_count} notes, skipped {skipped_count}. Attempting to write file...")
        pm.write(midi_filepath)
        print(f"Successfully created MIDI file using pretty_midi: '{midi_filepath}'")
    except IOError:
        print(f"Error: Could not write MIDI file to '{midi_filepath}'")
    except Exception as e:
        print(f"An unexpected error occurred while writing the MIDI file with pretty_midi: {e}")
        # Optionally print traceback for detailed debugging
        # import traceback
        # traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert JSON (with beats and tempo map) to MIDI using pretty_midi.")
    parser.add_argument("json_file", help="Path to the input JSON file.")
    parser.add_argument("midi_file", help="Path to the output MIDI file (e.g., output.mid).")

    args = parser.parse_args()
    json_to_midi(args.json_file, args.midi_file)