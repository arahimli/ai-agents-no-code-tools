from video.media import MediaUtils
import time
from loguru import logger


class VideoBuilder:
    """
    Builder class for constructing FFmpeg video commands with a fluent interface.
    """

    def __init__(self, dimensions: tuple[int, int], ffmpeg_path="ffmpeg"):
        if not isinstance(dimensions, tuple) or len(dimensions) != 2:
            raise ValueError("Dimensions must be a tuple of (width, height).")

        self.width, self.height = dimensions
        self.ffmpeg_path = ffmpeg_path

        # Components
        self.background = None
        self.audio_file = None
        self.captions = None
        self.output_path = "output.mp4"

        # Internal state
        self.media_utils = None

    def set_media_utils(self, media_utils: MediaUtils):
        """Set the media manager for duration calculations."""
        self.media_utils = media_utils
        return self

    def set_background_image(self, file_path: str, ken_burns_config: dict = None):
        """Set background as an image with optional Ken Burns effect."""
        self.background = {
            "type": "image",
            "file": file_path,
            "ken_burns": ken_burns_config or {},
        }
        return self

    def set_background_video(self, file_path: str):
        """Set background as a video file."""
        self.background = {"type": "video", "file": file_path}
        return self

    def set_audio(self, file_path: str):
        """Set audio file."""
        self.audio_file = file_path
        return self

    def set_captions(
        self,
        file_path: str = None,
        config: dict = None,
    ):
        """Set caption subtitles

        Args:
            file_path: Path to subtitle file 
            config: Optional configuration dict
        """
        self.captions = {
            "file": file_path,
            **(config or {}),
        }
        return self

    def set_output_path(self, output_path: str):
        """Set output file path."""
        self.output_path = output_path
        return self

    def build_command(self):
        """Build the complete FFmpeg command."""
        if not self.background:
            raise ValueError("Background must be set (image or video).")

        if not self.audio_file and not self.captions:
            raise ValueError(
                "At least one of audio_file, or captions must be provided."
            )

        # Validate combinations
        if self.background["type"] == "image" and not self.audio_file:
            raise ValueError("Audio file must be provided if background is an image.")

        if (
            self.background["type"] == "video"
            and not self.audio_file
            and self.captions is None
        ):
            raise ValueError(
                "Audio file or captions must be provided if background is a video."
            )

        # Get audio duration if audio file is provided
        audio_duration = None
        if self.audio_file:
            if not self.media_utils:
                raise ValueError(
                    "Media manager must be set to determine audio duration."
                )
            media_info = self.media_utils.get_audio_info(self.audio_file)
            audio_duration = media_info.get("duration")
            if not audio_duration:
                raise ValueError("Could not determine audio duration")

        # Build command
        cmd = [self.ffmpeg_path, "-y"]

        filter_parts = []
        input_index = 0

        # Add background input
        if self.background["type"] == "image":
            cmd.extend(
                ["-loop", "1", "-t", str(audio_duration), "-i", self.background["file"]]
            )

            # Ken Burns effect
            ken_burns_config = self.background.get("ken_burns", {})
            # direction = ken_burns_config.get("direction", "zoom-to-top")
            zoom_factor = ken_burns_config.get("zoom_factor", 0.001)

            # todo without upscaling we can't use the top and center zooms. upscaling increases the render time
            zoom_expressions = {
                "zoom-to-top": f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=0",
                "zoom-to-center": f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2)",
                "zoom-to-top-left": f"z='zoom+{zoom_factor}':x=0:y=0",
            }
            zoom_expr = zoom_expressions["zoom-to-top-left"]

            fps = 25
            duration_frames = int(audio_duration * fps)
            zoompan_d = duration_frames + 1
            filter_parts.append(
                f"[{input_index}]scale={self.width}:-2,setsar=1:1,"
                f"crop={self.width}:{self.height},"
                f"zoompan={zoom_expr}:d={zoompan_d}:s={self.width}x{self.height}:fps={fps}[bg]"
            )

        elif self.background["type"] == "video":
            if audio_duration:
                cmd.extend(
                    [
                        "-stream_loop",
                        "-1",
                        "-t",
                        str(audio_duration),
                        "-i",
                        self.background["file"],
                    ]
                )
            else:
                cmd.extend(["-i", self.background["file"]])
            filter_parts.append(f"[{input_index}]scale={self.width}:{self.height}[bg]")

        input_index += 1
        current_video = "[bg]"

        # Add audio input
        audio_input_index = None
        if self.audio_file:
            cmd.extend(["-i", self.audio_file])
            audio_input_index = input_index
            input_index += 1

        # Add subtitles or caption images if provided
        if self.captions:
            subtitle_file = self.captions.get("file")
            if subtitle_file:
                filter_parts.append(f"{current_video}subtitles={subtitle_file}[v]")
                current_video = "[v]"
        else:
            # Rename final video output
            if current_video == "[bg]":
                current_video = "[v]"
                filter_parts.append(f"[bg]copy[v]")

        # Build filter complex
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])

        # Map video and audio
        cmd.extend(["-map", current_video])
        if audio_input_index is not None:
            cmd.extend(["-map", f"{audio_input_index}:a"])

        # Video codec settings
        cmd.extend(["-c:v", "libx264", "-preset", "ultrafast"])

        cmd.extend(["-crf", "23", "-pix_fmt", "yuv420p"])

        # Audio codec settings
        if self.audio_file:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            if audio_duration:
                cmd.extend(["-t", str(audio_duration)])

        cmd.append(self.output_path)
        return cmd

    def execute(self):
        """Build and execute the FFmpeg command using MediaUtils for progress tracking."""
        if not self.media_utils:
            logger.error("MediaUtils must be set before executing video build")
            return False

        start = time.time()
        context_logger = logger.bind(
            dimensions=(self.width, self.height),
            background_type=self.background.get("type") if self.background else None,
            has_audio=bool(self.audio_file),
            has_captions=bool(self.captions),
            output_path=self.output_path,
            youtube_channel="https://www.youtube.com/@aiagentsaz"
        )

        try:
            context_logger.debug("building video with VideoBuilder")
            cmd = self.build_command()

            # Calculate expected duration for progress tracking
            expected_duration = None
            if self.audio_file:
                audio_info = self.media_utils.get_audio_info(self.audio_file)
                expected_duration = audio_info.get("duration")
            elif self.background and self.background.get("type") == "video":
                video_info = self.media_utils.get_video_info(self.background["file"])
                expected_duration = video_info.get("duration")

            context_logger.bind(
                command=" ".join(cmd),
                expected_duration=expected_duration,
            ).debug("executing video build command")
            # Execute using MediaUtils for proper logging and progress tracking
            success = self.media_utils.execute_ffmpeg_command(
                cmd,
                "build video",
                expected_duration=expected_duration,
                show_progress=True,
            )

            if success:
                context_logger.bind(execution_time=time.time() - start).info(
                    "video built successfully"
                )
                return True
            else:
                context_logger.error("failed to build video")
                return False

        except Exception as e:
            context_logger.bind(error=str(e), execution_time=time.time() - start).error(
                "error during video rendering"
            )
            return False
