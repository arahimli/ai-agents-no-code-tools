import string
from typing import List, Dict, Tuple
from loguru import logger

from typing import Dict, List


class Caption:
    def is_punctuation(self, text):
        return text in string.punctuation

    def create_subtitle_segments_english(
        self, captions: List[Dict], max_length=80, lines=2
    ):
        """
        Breaks up the captions into segments of max_length characters
        on two lines and merge punctuation with the last word
        """

        if not captions:
            return []

        segments = []
        current_segment_texts = ["" for _ in range(lines)]
        current_line = 0
        segment_start_ts = captions[0]["start_ts"]
        segment_end_ts = captions[0]["end_ts"]

        for caption in captions:
            text = caption["text"]
            start_ts = caption["start_ts"]
            end_ts = caption["end_ts"]

            # Update the segment end timestamp
            segment_end_ts = end_ts

            # If the caption is a punctuation, merge it with the current line
            if self.is_punctuation(text):
                if current_line < lines and current_segment_texts[current_line]:
                    current_segment_texts[current_line] += text
                continue

            # If the line is too long, move to the next one
            if (
                current_line < lines
                and len(current_segment_texts[current_line] + text) > max_length
            ):
                current_line += 1

            # If we've filled all lines, save the current segment and start a new one
            if current_line >= lines:
                segments.append(
                    {
                        "text": current_segment_texts,
                        "start_ts": segment_start_ts,
                        "end_ts": segment_end_ts,
                    }
                )

                # Reset for next segment
                current_segment_texts = ["" for _ in range(lines)]
                current_line = 0
                # Add a small gap (0.05s) between segments to prevent overlap
                segment_start_ts = start_ts + 0.05

            # Add the text to the current segment
            if current_line < lines:
                current_segment_texts[current_line] += (
                    " " if current_segment_texts[current_line] else ""
                )
                current_segment_texts[current_line] += text

        # Add the last segment if there's any content
        if any(current_segment_texts):
            segments.append(
                {
                    "text": current_segment_texts,
                    "start_ts": segment_start_ts,
                    "end_ts": segment_end_ts,
                }
            )

        # Post-processing to ensure no overlaps by adjusting end times if needed
        for i in range(len(segments) - 1):
            if segments[i]["end_ts"] >= segments[i + 1]["start_ts"]:
                segments[i]["end_ts"] = segments[i + 1]["start_ts"] - 0.05

        return segments

    def create_subtitle(
        self,
        segments,
        dimensions: Tuple[int, int],
        output_path: str,
        position_from_top=0.4,
        font_size=24, 
        font_color="&H00FFFFFF",
        shadow_color="&H80000000",
        shadow_blur=0,
        stroke_color="&H00000000",
        stroke_size=0
    ):
        # Create the .ass subtitle file with headers
        width, height = dimensions
        ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{font_color},&H000000FF,{stroke_color},&H00000000,-1,0,0,0,100,100,0,0,1,{stroke_size},0,8,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(
            width=width,
            height=height,
            font_size=font_size,
            font_color=font_color,
            stroke_color=stroke_color,
            stroke_size=stroke_size,
        )

        pos_x = int(width / 2)
        pos_y = int(height * position_from_top)

        # Process each segment and add to the subtitle file
        for segment in segments:
            start_time = self.format_time(segment["start_ts"])
            end_time = self.format_time(segment["end_ts"])

            # Create text with line breaks
            text_lines = segment["text"]
            formatted_text = ""
            for i, line in enumerate(text_lines):
                if line:  # Only add non-empty lines
                    if i > 0:  # Add line break if not the first line
                        formatted_text += "\\N"
                    formatted_text += line

            if shadow_blur > 0:
                shadow_color_opaque = shadow_color.replace("&H80", "&H00")
                shadow_override_tags = f"\\pos({pos_x},{pos_y})\\1c{shadow_color_opaque}\\3c&H00000000\\4c&H00000000"
                
                if shadow_blur > 0:
                    shadow_override_tags += f"\\blur{shadow_blur}"
                
                shadow_formatted_text = f"{{{shadow_override_tags}}}" + formatted_text
                
                # Add shadow dialogue line first (so it appears behind)
                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{shadow_formatted_text}\n"

            # Create main text layer
            main_override_tags = f"\\pos({pos_x},{pos_y})"
            main_formatted_text = f"{{{main_override_tags}}}" + formatted_text

            # Add main dialogue line (appears on top)
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{main_formatted_text}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        logger.debug("subtitle (ass) was created with drop shadow")

    def format_time(self, seconds):
        """
        Convert seconds to ASS time format (H:MM:SS.cc)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)

        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
