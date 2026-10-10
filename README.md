# Seerr-Linker

A lightweight Python Flask webhook listener designed for the `*arr` ecosystem. It intercepts "Media Available" payloads from Seerr/Jellyseerr and automatically generates Linux hard links from a shared download pool to isolated user directories. 

This enables multi-user privacy in Jellyfin/Plex without wasting physical storage space on duplicate media files.

## How It Works (The Logic)
1. **The Request:** A user (e.g., `user_1`) requests a movie via the Seerr interface.
2. **The Download:** Seerr sends the request to Radarr/Sonarr, which downloads and imports the media into a shared pool directory (`all_downloads`). 
3. **The Trigger:** Seerr detects that Radarr/Sonarr has successfully imported the file. Seerr then fires a `MEDIA_AVAILABLE` JSON webhook payload to the Seerr-Linker container.
4. **The Linker:** 
   * The Python script intercepts the payload and extracts the media title, media type (movie vs. tv), and the username of the requester.
   * It scans the `all_downloads` directory for the matching media folder.
   * Instead of copying the file (which wastes disk space), it executes a recursive `os.link` command. This creates a hard link in the requesting user's private directory (e.g., `/movies/user_1/`).
5. **The Result:** The media exists in both `all_downloads` and `user_1`, but only occupies physical storage space once. Jellyfin scans the `user_1` directory, granting them exclusive access to the media they requested.

## Prerequisites
1. **Linux Native Filesystem:** The target storage drive must be formatted as `ext4`, `btrfs`, or `zfs`. Hard links are not supported across different filesystems or standard Windows formats (NTFS/exFAT) when mounted in Linux.
2. **Unified Volume Mount:** Radarr, Sonarr, and Seerr-Linker must all mount the exact same parent directory structure in Docker (e.g., `/mnt/storage:/data`). Hard links cannot cross Docker volume boundaries.

## Directory Structure Requirement
The container expects the following directory structure inside the mapped volume:

```text
/data/media/video/
├── movies/
│   ├── all_downloads/    <-- Radarr Root Folder
│   ├── user_1/             <-- Script links user_1's requested movies here
│   └── user_2/             <-- Script links user_2's requested movies here
└── tv_shows/
    ├── all_downloads/    <-- Sonarr Root Folder
    ├── user_1/             <-- Script links user_1's requested shows here
    └── user_2/             <-- Script links user_2's requested shows here