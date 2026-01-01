"""Retrieve YouTube video list - Get all videos from a YouTube channel."""

from pathlib import Path
from typing import Optional

import click
import yaml

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS format.

    Args:
        seconds: Duration in seconds (can be int or float), or None if unknown

    Returns:
        Formatted duration string
    """
    if seconds is None:
        return "Unknown"

    # Convert to integer for formatting
    total_seconds = int(seconds)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_channel_videos(channel_url: str, max_videos: Optional[int] = None) -> list:
    """Retrieve all videos from a YouTube channel.

    Args:
        channel_url: URL of the YouTube channel (can be channel URL, handle, or channel ID)
        max_videos: Maximum number of videos to retrieve (None for all)

    Returns:
        List of video dictionaries with title, duration, and url
    """
    if yt_dlp is None:
        raise ImportError("yt-dlp is required. Install with: pip install yt-dlp")

    # Configure yt-dlp options
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Don't download, just extract info
        'ignoreerrors': True,  # Skip unavailable videos
    }

    if max_videos:
        ydl_opts['playlistend'] = max_videos

    videos = []

    # Normalize channel URL to videos tab
    if '/videos' not in channel_url:
        if channel_url.endswith('/'):
            channel_url = channel_url + 'videos'
        else:
            channel_url = channel_url + '/videos'

    click.echo(click.style(f"Fetching videos from: {channel_url}", fg="blue"))

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Extract channel info
            result = ydl.extract_info(channel_url, download=False)

            if result is None:
                click.echo(click.style("Error: Could not extract channel info", fg="red"))
                return []

            # Handle playlist/channel entries
            entries = result.get('entries', [])
            if not entries:
                click.echo(click.style("No videos found in channel", fg="yellow"))
                return []

            click.echo(click.style(f"Found {len(entries)} video(s)", fg="green"))

            for entry in entries:
                if entry is None:
                    continue

                video_id = entry.get('id', '')
                title = entry.get('title', 'Unknown Title')
                duration = entry.get('duration')  # Duration in seconds

                # Construct video URL
                video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get('url', '')

                videos.append({
                    'title': title,
                    'duration': format_duration(duration),
                    'duration_seconds': duration,
                    'url': video_url,
                })

        except Exception as e:
            click.echo(click.style(f"Error fetching channel: {e}", fg="red"))
            return []

    return videos


@click.command(name="retrieve_youtube_video_list")
@click.argument("channel_url")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="youtube_videos.yaml",
    help="Output YAML file path (default: youtube_videos.yaml)",
)
@click.option(
    "--max-videos",
    "-m",
    type=int,
    default=None,
    help="Maximum number of videos to retrieve (default: all)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show verbose output with video details",
)
def retrieve_youtube_video_list(channel_url: str, output: Path, max_videos: Optional[int], verbose: bool):
    """Retrieve all videos from a YouTube channel and save to YAML file.

    CHANNEL_URL can be:
    - Full channel URL: https://www.youtube.com/channel/UC...
    - Channel handle: https://www.youtube.com/@channelname
    - Custom URL: https://www.youtube.com/c/channelname

    Examples:
        n4_cli retrieve_youtube_video_list https://www.youtube.com/@channelname
        n4_cli retrieve_youtube_video_list https://www.youtube.com/@channelname -o my_videos.yaml
        n4_cli retrieve_youtube_video_list https://www.youtube.com/@channelname -m 50 -v
    """
    if yt_dlp is None:
        click.echo(click.style("Error: yt-dlp is not installed.", fg="red"))
        click.echo(click.style("Install it with: pip install yt-dlp", fg="yellow"))
        raise click.Abort()

    click.echo(click.style(f"\nYouTube Video List Retriever", fg="cyan", bold=True))
    click.echo(click.style("=" * 40, fg="cyan"))

    # Retrieve videos
    videos = get_channel_videos(channel_url, max_videos)

    if not videos:
        click.echo(click.style("\nNo videos retrieved.", fg="yellow"))
        return

    # Display videos if verbose
    if verbose:
        click.echo(click.style(f"\nVideos:", fg="blue", bold=True))
        for i, video in enumerate(videos, 1):
            click.echo(f"  {i}. {video['title']}")
            click.echo(click.style(f"     Duration: {video['duration']}", fg="gray"))
            click.echo(click.style(f"     URL: {video['url']}", fg="gray"))

    # Prepare output data
    output_data = {
        'channel_url': channel_url,
        'total_videos': len(videos),
        'videos': [
            {
                'title': v['title'],
                'duration': v['duration'],
                'url': v['url'],
            }
            for v in videos
        ]
    }

    # Save to YAML file
    try:
        with open(output, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        click.echo(click.style(f"\nSaved {len(videos)} video(s) to: {output}", fg="green", bold=True))

        # Show summary
        total_duration = sum(v.get('duration_seconds') or 0 for v in videos)
        click.echo(click.style(f"Total duration: {format_duration(total_duration)}", fg="blue"))

    except IOError as e:
        click.echo(click.style(f"Error writing to file: {e}", fg="red"))
        raise click.Abort()
