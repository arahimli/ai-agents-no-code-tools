import subprocess
import json
import time
from loguru import logger


class MediaUtils:
    def __init__(self, ffmpeg_path="ffmpeg"):
        """
        Initializes the MediaUtils class.

        Args:
            ffmpeg_path: Path to the ffmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path

    def merge_videos(
        self,
        video_paths: list,
        output_path: str,
        background_music_path: str = None,
        background_music_volume: float = 0.5,
    ) -> bool:
        """
        Merges multiple video files into one, optionally with background music.

        Args:
            video_paths: List of paths to video files to merge
            output_path: Path for the merged output video
            background_music: Optional path to background music file
            bg_music_volume: Volume level for background music (0.0 to 1.0, default 0.5)

        Returns:
            bool: True if successful, False otherwise
        """
        if not video_paths:
            logger.error("no video paths provided for merging")
            return False

        start = time.time()
        context_logger = logger.bind(
            number_of_videos=len(video_paths),
            output_path=output_path,
            background_music=bool(background_music_path),
            background_music_volume=background_music_volume,
        )

        try:
            # Get dimensions from the first video
            first_video_info = self.get_video_info(video_paths[0])
            if not first_video_info:
                context_logger.error("failed to get video info from first video")
                return False

            target_width = first_video_info.get("width", 1080)
            target_height = first_video_info.get("height", 1920)
            target_dimensions = f"{target_width}:{target_height}"

            context_logger.bind(
                target_width=target_width, target_height=target_height
            ).debug("using dimensions from first video")

            # Base command
            cmd = [self.ffmpeg_path, "-y"]

            # Add input video files
            for video_path in video_paths:
                cmd.extend(["-i", video_path])

            # Add background music if provided
            music_input_index = None
            if background_music_path:
                cmd.extend(["-i", background_music_path])
                music_input_index = len(video_paths)

            # Create filter complex for concatenating videos with re-encoding
            if len(video_paths) == 1:
                # Single video - re-encode to ensure consistency
                if background_music_path:
                    cmd.extend(
                        [
                            "-filter_complex",
                            f"[0:v]scale={target_dimensions}:force_original_aspect_ratio=decrease,pad={target_dimensions}:(ow-iw)/2:(oh-ih)/2:black,fps=30[v];[{music_input_index}:a]volume={background_music_volume}[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-filter_complex",
                            f"[0:v]scale={target_dimensions}:force_original_aspect_ratio=decrease,pad={target_dimensions}:(ow-iw)/2:(oh-ih)/2:black,fps=30[v]",
                            "-map",
                            "[v]",
                            "-map",
                            "0:a",
                        ]
                    )
            else:
                # Multiple videos - normalize and concatenate with re-encoding
                # First, create normalized video streams for each input
                normalize_filters = []
                for i in range(len(video_paths)):
                    normalize_filters.append(
                        f"[{i}:v]scale={target_dimensions}:force_original_aspect_ratio=decrease,pad={target_dimensions}:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p[v{i}n]"
                    )

                # Create the concat filter using normalized streams
                concat_inputs = ""
                for i in range(len(video_paths)):
                    concat_inputs += f"[v{i}n][{i}:a]"

                # Combine all filters
                filter_complex = (
                    ";".join(normalize_filters)
                    + f";{concat_inputs}concat=n={len(video_paths)}:v=1:a=1[v][a]"
                )

                if background_music_path:
                    # Mix the concatenated audio with background music
                    filter_complex += f";[{music_input_index}:a]volume={background_music_volume}[bg];[a][bg]amix=inputs=2:duration=first[final_a]"
                    cmd.extend(
                        [
                            "-filter_complex",
                            filter_complex,
                            "-map",
                            "[v]",
                            "-map",
                            "[final_a]",
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-filter_complex",
                            filter_complex,
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                        ]
                    )

            # Video codec settings
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                ]
            )

            # Audio codec settings
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            # Other settings
            cmd.extend(["-pix_fmt", "yuv420p", output_path])

            # Execute the command using the new method

            # calculate expected duration for progress tracking
            expected_duration = 0
            for video_path in video_paths:
                video_info = self.get_video_info(video_path)
                expected_duration += video_info.get("duration", 0)

            success = self.execute_ffmpeg_command(
                cmd,
                "merge videos",
                expected_duration=expected_duration,
                show_progress=True,
            )

            if success:
                context_logger.bind(execution_time=time.time() - start).debug(
                    "videos merged successfully",
                )
                return True
            else:
                context_logger.error("ffmpeg failed to merge videos")
                return False

        except Exception as e:
            context_logger.bind(error=str(e)).error(
                "error merging videos",
            )
            return False

    def get_video_info(self, file_path: str) -> dict:
        """
        Retrieves video information such as duration, width, height, codec, fps, etc.

        Args:
            file_path: Path to the video file

        Returns:
            Dictionary containing video information
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                "-select_streams",
                "v:0",  # Select first video stream
                file_path,
            ]

            success, stdout, stderr = self.execute_ffprobe_command(
                cmd, "get video info"
            )

            if not success:
                raise Exception(f"ffprobe failed: {stderr}")

            probe_data = json.loads(stdout)

            # Extract format information
            format_info = probe_data.get("format", {})
            streams = probe_data.get("streams", [])

            if not streams:
                raise Exception("No video stream found in file")

            video_stream = streams[0]

            video_info = {
                "duration": float(format_info.get("duration", 0)),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
            }

            return video_info

        except Exception as e:
            logger.bind(file_path=file_path, error=str(e)).error(
                "error getting video info"
            )
            return {}

    def get_audio_info(self, file_path: str) -> dict:
        """
        Retrieves audio information such as duration, codec, bitrate, sample rate, channels, etc.

        Args:
            file_path: Path to the audio file

        Returns:
            Dictionary containing audio information
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                "-select_streams",
                "a:0",  # Select first audio stream
                file_path,
            ]

            success, stdout, stderr = self.execute_ffprobe_command(
                cmd, "get audio info"
            )

            if not success:
                raise Exception(f"ffprobe failed: {stderr}")

            probe_data = json.loads(stdout)

            # Extract format information
            format_info = probe_data.get("format", {})
            streams = probe_data.get("streams", [])

            if not streams:
                raise Exception("No audio stream found in file")

            audio_stream = streams[0]

            audio_info = {
                "duration": float(format_info.get("duration", 0)),
                "channels": audio_stream.get("channels", 0),
            }

            return audio_info

        except Exception as e:
            logger.bind(file_path=file_path, error=str(e)).error(
                "Error getting audio info"
            )
            return {}

    def format_time(self, seconds: float) -> str:
        """
        Format seconds into HH:MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def execute_ffmpeg_command(
        self,
        cmd: list,
        operation_name: str,
        expected_duration: float = None,
        show_progress: bool = True,
    ) -> bool:
        """
        Execute an ffmpeg command with proper logging and progress tracking.

        Args:
            cmd: The ffmpeg command as a list
            operation_name: Name of the operation for logging
            expected_duration: Expected duration for progress calculation
            show_progress: Whether to show progress information

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.bind(command=" ".join(cmd), operation=operation_name).debug(
                f"executing ffmpeg command for {operation_name}"
            )

            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                text=True,
            )

            # Process the output line by line as it becomes available
            for line in process.stderr:
                # Extract time information for progress tracking
                if (
                    show_progress
                    and expected_duration
                    and "time=" in line
                    and "speed=" in line
                ):
                    try:
                        # Extract the time information
                        time_str = line.split("time=")[1].split(" ")[0]
                        # Convert HH:MM:SS.MS format to seconds
                        h, m, s = time_str.split(":")
                        seconds = float(h) * 3600 + float(m) * 60 + float(s)

                        # Calculate progress percentage
                        progress = min(100, (seconds / expected_duration) * 100)
                        logger.info(
                            f"{operation_name}: {progress:.2f}% complete (Time: {time_str} / Total: {self.format_time(expected_duration)})"
                        )
                    except (ValueError, IndexError):
                        # If parsing fails, continue silently
                        pass
                elif any(
                    keyword in line
                    for keyword in [
                        # Skip initialization information
                        "ffmpeg version",
                        "built with",
                        "configuration:",
                        "libav",
                        "Input #",
                        "Metadata:",
                        "Duration:",
                        "Stream #",
                        "Press [q]",
                        "Output #",
                        "Stream mapping:",
                        # Skip processing details
                        "frame=",
                        "fps=",
                        "[libx264",
                        "kb/s:",
                        "Qavg:",
                        "video:",
                        "audio:",
                        "subtitle:",
                        "frame I:",
                        "frame P:",
                        "mb I",
                        "mb P",
                        "coded y,",
                        "i16 v,h,dc,p:",
                        "i8c dc,h,v,p:",
                        "compatible_brands:",
                        "encoder",
                        "Side data:",
                        "libswscale",
                        "libswresample",
                        "libpostproc",
                        # Additional patterns to filter
                        "ffmpeg: libswscale",
                        "ffmpeg: libswresample",
                        "ffmpeg: libpostproc",
                    ]
                ):
                    # Skip all technical output lines
                    pass
                else:
                    # Only print important messages (like errors and warnings)
                    # that don't match any of the filtered patterns
                    if not line.strip() or line.strip().startswith("["):
                        continue

                    # Skip header lines that describe inputs
                    if ":" in line and any(
                        header in line
                        for header in [
                            "major_brand",
                            "minor_version",
                            "creation_time",
                            "handler_name",
                            "vendor_id",
                            "Duration",
                            "bitrate",
                        ]
                    ):
                        continue

                    logger.debug(f"ffmpeg: {line.strip()}")

            # Wait for the process to complete and check the return code
            return_code = process.wait()
            if return_code != 0:
                logger.bind(return_code=return_code, operation=operation_name).error(
                    f"ffmpeg exited with code: {return_code} for {operation_name}"
                )
                return False

            logger.bind(operation=operation_name).debug(
                f"{operation_name} completed successfully"
            )
            return True

        except Exception as e:
            logger.bind(error=str(e), operation=operation_name).error(
                f"error executing ffmpeg command for {operation_name}"
            )
            return False

    def execute_ffprobe_command(
        self, cmd: list, operation_name: str
    ) -> tuple[bool, str, str]:
        """
        Execute an ffprobe command with proper logging.

        Args:
            cmd: The ffprobe command as a list
            operation_name: Name of the operation for logging

        Returns:
            tuple: (success, stdout, stderr)
        """
        try:
            logger.bind(command=" ".join(cmd), operation=operation_name).debug(
                f"executing ffprobe command for {operation_name}"
            )

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.bind(stderr=stderr, operation=operation_name).error(
                    f"ffprobe failed for {operation_name}"
                )
                return False, stdout, stderr

            logger.bind(operation=operation_name).debug(
                f"{operation_name} completed successfully"
            )
            return True, stdout, stderr

        except Exception as e:
            logger.bind(error=str(e), operation=operation_name).error(
                f"error executing ffprobe command for {operation_name}"
            )
            return False, "", str(e)
