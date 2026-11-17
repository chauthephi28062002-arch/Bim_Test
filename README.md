# Windows File Renamer

A Windows desktop batch renamer built with Python and CustomTkinter. It supports
local, external, and network folders accessible to the current Windows account.
The app only lists files directly inside the selected folder; it does not recurse
into subfolders.

## Features

- Browse to a folder or enter a path such as `C:\Photos`, `D:\Exports`, or a UNC
  network path such as `\\server\share\folder`.
- Filter by one or more extensions, for example `.jpg,.png`; leave blank for all
  files.
- Check individual files, select all visible files, rename checked files, or
  rename every file in the current filtered view. Clear the extension filter to
  include every file in the folder.
- Add prefixes/suffixes, find and replace text, remove an exact text string, apply
  capitalization, and optionally add sequential numbers.
- Preview original and proposed names, with invalid names and conflicts
  highlighted before execution. File extensions are preserved.
- Validate Windows filename rules, prevent duplicate targets and refuse to
  overwrite existing files.
- Confirm each batch, undo the most recent successful batch, and persist the
  rename history between launches.

## Installation (Windows)

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/).
   Enable **Add Python to PATH** in the installer.
2. Open PowerShell in this folder:

   ```powershell
   cd D:\BIM_Tools\WindowsFileRenamer
   ```

3. (Recommended) Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies and launch:

   ```powershell
   py -m pip install -r requirements.txt
   py main.py
   ```

On first launch, Windows may ask whether to allow network access; the app does
not start a network service. It accesses network folders only when you select
them through the file dialog or enter a path.

## Safety and history

Every rename requires a confirmation. Renames are staged through temporary
filenames to handle batch operations safely, including case-only changes and
swaps. History is saved to
`%LOCALAPPDATA%\WindowsFileRenamer\history.json`. Undo restores the latest
batch only and will stop rather than overwrite a file that has appeared at an
original path since the rename.

The app is intended for Windows. Test a new set of rename rules on sample files
before applying them to important data.
