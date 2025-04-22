import pretty_midi
import json
import argparse
import os

# Helper function to convert ticks to beats
def ticks_to_beats(ticks, resolution):
    return float(ticks) / resolution

def midi_to_json(midi_file_path, output_path=None, format="pretty"):
    """
    Convert a MIDI file to a JSON representation, including notes (in beats)
    and the tempo map.

    The output JSON will be an object with keys:
    - "resolution": Ticks per quarter note (PPQN) from the MIDI file.
    - "tempo_map": List of tempo changes [{"beat": float_beat, "bpm": float_bpm}].
    - "notes": A list of note objects, each with "pitch", "start_beat" (float),
               "duration_beat" (float), and "velocity".

    Parameters:
    -----------
    midi_file_path : str
        Path to the input MIDI file
    output_path : str, optional
        Path to save the output JSON file. If None, uses the same name as MIDI file
    format : str
        Output format: "pretty" (indented) or "compact" (single line)

    Returns:
    --------
    str
        The path to the created JSON file, or None if an error occurred.
    """
    try:
        # Load the MIDI file
        pm = pretty_midi.PrettyMIDI(midi_file_path)
        resolution = pm.resolution # Ticks per quarter note
    except FileNotFoundError:
        print(f"Error: Input MIDI file not found: {midi_file_path}")
        return None
    except Exception as e:
        print(f"Error loading MIDI file {midi_file_path}: {e}")
        return None

    # Get the tempo changes and convert times to beats
    tempo_map = []
    try:
        tempo_change_times, tempo_change_bpm = pm.get_tempo_changes()
        # Get ticks for each tempo change time
        tempo_change_ticks = [pm.time_to_tick(t) for t in tempo_change_times]
        # Convert ticks to beats
        tempo_change_beats = [ticks_to_beats(tick, resolution) for tick in tempo_change_ticks]
        # Create the tempo map
        tempo_map = [{"beat": beat, "bpm": float(bpm)} for beat, bpm in zip(tempo_change_beats, tempo_change_bpm)]
        # Ensure tempo map is sorted by beat (should be already, but just in case)
        tempo_map.sort(key=lambda x: x['beat'])
        # Make sure there's a tempo event at beat 0 if the first isn't already there
        if not tempo_map or tempo_map[0]['beat'] > 0:
            # If no tempos found, use a default. Otherwise, use the first tempo found.
            initial_bpm = tempo_map[0]['bpm'] if tempo_map else 120.0
            tempo_map.insert(0, {"beat": 0.0, "bpm": initial_bpm})

    except Exception as e:
        print(f"Warning: Could not read tempo information. Error: {e}")
        # Add a default tempo at beat 0 if map is empty
        if not tempo_map:
             tempo_map.append({"beat": 0.0, "bpm": 120.0})


    all_notes_data = []
    total_notes = 0
    for instrument_num, instrument in enumerate(pm.instruments):
        for note in instrument.notes:
            # Convert start and end times (seconds) to ticks, then to beats
            start_tick = pm.time_to_tick(note.start)
            end_tick = pm.time_to_tick(note.end)

            start_beat = ticks_to_beats(start_tick, resolution)
            end_beat = ticks_to_beats(end_tick, resolution)
            duration_beat = end_beat - start_beat

            # Ensure duration is positive (can happen with very short notes + float precision)
            if duration_beat <= 0:
                # Assign a minimal duration instead of skipping
                duration_beat = ticks_to_beats(1, resolution) # Duration of one tick

            note_data = {
                "pitch": int(note.pitch),
                "start_beat": start_beat,
                "duration_beat": duration_beat,
                "velocity": int(note.velocity),
                "track": instrument_num # Add track info based on instrument index
            }
            all_notes_data.append(note_data)
            total_notes += 1

    # Sort notes by start beat
    all_notes_data.sort(key=lambda x: x['start_beat'])

    # Prepare the final JSON structure
    output_data = {
        "resolution": resolution,
        "tempo_map": tempo_map,
        "notes": all_notes_data
    }

    # Convert to JSON with appropriate formatting
    indent_value = 4 if format == "pretty" else None
    try:
        json_str = json.dumps(output_data, indent=indent_value)
    except Exception as e:
        print(f"Error converting data to JSON: {e}")
        return None

    # Determine output path
    if output_path is None:
        output_path = os.path.splitext(midi_file_path)[0] + ".json"

    # Save the JSON file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    except IOError as e:
        print(f"Error writing JSON file to {output_path}: {e}")
        return None

    initial_tempo_display = tempo_map[0]['bpm'] if tempo_map else "N/A"
    print(f"Saved MIDI data (PPQN: {resolution}, Initial Tempo: {initial_tempo_display:.2f} BPM) as JSON to: {output_path}")
    print(f"Total instruments processed (used as tracks): {len(pm.instruments)}")
    print(f"Total notes converted: {total_notes}")
    print(f"Tempo changes detected: {len(tempo_map)}")

    return output_path

def main():
    parser = argparse.ArgumentParser(description="Convert MIDI file to JSON format (list of notes).")
    parser.add_argument("input_file", help="Path to input MIDI file")
    parser.add_argument("--output", "-o", help="Path to output JSON file (optional)")
    parser.add_argument("--format", choices=["pretty", "compact"], default="pretty",
                        help="Output format: pretty (indented) or compact (single line)")

    args = parser.parse_args()

    # Convert MIDI to JSON
    midi_to_json(args.input_file, args.output, args.format)

if __name__ == "__main__":
    main()