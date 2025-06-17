from .video_editing import concatenate_clips


def concatenate_standard(clips_dir: str, out_path: str) -> None:
    """Concatenate clips using the standard white flash transition."""
    concatenate_clips(clips_dir, out_path)
