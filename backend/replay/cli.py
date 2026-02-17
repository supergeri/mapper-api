"""
Replay Engine CLI - Command-line interface for session replay and diffing.

Usage:
    python -m replay run <session>     - Replay a session and show diff output
    python -m replay diff <a> <b>      - Compare two sessions side by side
    python -m replay list               - List all sessions with hop count and health
    python -m replay validate <session> - Validate session (check for missing hops)
    python -m replay tags              - Show all tags across scenarios
    python -m replay save <name>       - Save current capture as named scenario
"""

from __future__ import annotations

import argparse
import re
import sys
import json
from pathlib import Path
from typing import Optional

from backend.replay.core import (
    Session, ReplayEngine, DiffEngine, IgnoreConfig, DiffItem
)


# Session name validation pattern: alphanumeric, underscore, dash only
SESSION_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_session_name(session_name: str) -> bool:
    """Validate session name to prevent path traversal attacks."""
    if not session_name:
        return False
    if '..' in session_name or '/' in session_name or '\\' in session_name:
        return False
    return SESSION_NAME_PATTERN.match(session_name) is not None


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def get_sessions_dir() -> Path:
    """Get the sessions directory, creating it if needed."""
    # Default to ~/.replay/sessions
    sessions_dir = Path.home() / '.replay' / 'sessions'
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def get_ignore_config(session_name: Optional[str] = None) -> IgnoreConfig:
    """Get ignore config, checking for session-specific .replayignore."""
    # Check for session-specific ignore file
    if session_name:
        session_ignore = get_sessions_dir() / f'.{session_name}.replayignore'
        if session_ignore.exists():
            return IgnoreConfig.from_file(session_ignore)
    
    # Check for global ignore file
    global_ignore = get_sessions_dir() / '.replayignore'
    return IgnoreConfig.from_file(global_ignore)


def format_diff_item(item: DiffItem, color: bool = True) -> str:
    """Format a single diff item for display."""
    c = Colors if color else type('NoColor', (), {
        'RESET': '', 'RED': '', 'GREEN': '', 'YELLOW': '',
        'BLUE': '', 'MAGENTA': '', 'CYAN': '', 'BOLD': '', 'DIM': ''
    })()
    
    symbols = {
        'added': f'{c.GREEN}+{c.RESET}',
        'removed': f'{c.RED}-{c.RESET}',
        'changed': f'{c.YELLOW}~{c.RESET}',
        'reordered': f'{c.CYAN}<>{c.RESET}'
    }
    
    symbol = symbols.get(item.diff_type, '?')
    
    if item.diff_type == 'added':
        value_display = f"{c.GREEN}{item.value_b}{c.RESET}"
    elif item.diff_type == 'removed':
        value_display = f"{c.RED}{item.value_a}{c.RESET}"
    elif item.diff_type == 'reordered':
        value_display = f"{c.CYAN}{item.value_a} -> {item.value_b}{c.RESET}"
    else:
        value_display = f"{c.YELLOW}{item.value_a} -> {item.value_b}{c.RESET}"
    
    return f"  {symbol} {item.path}: {value_display}"


def cmd_run(args):
    """Run/replay a session and show colored diff output."""
    # Validate session name to prevent path traversal
    if not validate_session_name(args.session):
        print(f"Error: Invalid session name '{args.session}'. Use alphanumeric characters, underscores, or dashes only.", file=sys.stderr)
        sys.exit(2)
    
    sessions_dir = get_sessions_dir()
    engine = ReplayEngine(sessions_dir)
    ignore_config = get_ignore_config(args.session)
    
    try:
        session = engine.load_session(args.session)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    
    # If no baseline provided, just show the session data
    if args.baseline:
        try:
            baseline_session = engine.load_session(args.baseline)
            diff_engine = DiffEngine(ignore_config)
            result = diff_engine.compute_diff(baseline_session, session)
            
            if result.identical:
                print(f"{Colors.GREEN}✓ Sessions are identical{Colors.RESET}")
                sys.exit(0)
            else:
                print(f"{Colors.BOLD}Differences from '{args.baseline}' to '{args.session}':{Colors.RESET}\n")
                for item in result.differences:
                    print(format_diff_item(item))
                sys.exit(1)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        # Just show session info
        print(f"{Colors.BOLD}Session: {session.name}{Colors.RESET}")
        print(f"ID: {session.id}")
        if session.tags:
            print(f"Tags: {', '.join(session.tags)}")
        if session.hops:
            print(f"Hops: {len(session.hops)}")
        print(f"\n{Colors.BOLD}Data:{Colors.RESET}")
        print(json.dumps(session.data, indent=2))


def cmd_diff(args):
    """Compare two sessions side by side."""
    # Validate session names to prevent path traversal
    if not validate_session_name(args.session_a):
        print(f"Error: Invalid session name '{args.session_a}'. Use alphanumeric characters, underscores, or dashes only.", file=sys.stderr)
        sys.exit(2)
    if not validate_session_name(args.session_b):
        print(f"Error: Invalid session name '{args.session_b}'. Use alphanumeric characters, underscores, or dashes only.", file=sys.stderr)
        sys.exit(2)
    
    sessions_dir = get_sessions_dir()
    engine = ReplayEngine(sessions_dir)
    ignore_config = get_ignore_config()
    diff_engine = DiffEngine(ignore_config)
    
    try:
        session_a = engine.load_session(args.session_a)
        session_b = engine.load_session(args.session_b)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    
    result = diff_engine.compute_diff(session_a, session_b)
    
    if result.identical:
        print(f"{Colors.GREEN}✓ Sessions are identical{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.BOLD}Diff: {args.session_a} vs {args.session_b}{Colors.RESET}\n")
        for item in result.differences:
            print(format_diff_item(item))
        
        print(f"\n{Colors.DIM}Total: {len(result.differences)} difference(s){Colors.RESET}")
        sys.exit(1)


def cmd_list(args):
    """List all sessions with hop count and health indicator."""
    sessions_dir = get_sessions_dir()
    engine = ReplayEngine(sessions_dir)
    sessions = engine.list_sessions()
    
    if not sessions:
        print("No sessions found.")
        return
    
    print(f"{Colors.BOLD}{'Name':<30} {'Hops':<8} {'Health':<20} {'Tags':<20}{Colors.RESET}")
    print("-" * 80)
    
    for session in sessions:
        health = engine.get_session_health(session)
        
        # Format health status with color
        status = health['status']
        if status == 'valid':
            health_str = f"{Colors.GREEN}✓ valid{Colors.RESET}"
        elif status == 'valid_with_gaps':
            health_str = f"{Colors.YELLOW}⚠ valid (gaps){Colors.RESET}"
        else:
            health_str = f"{Colors.RED}✗ invalid{Colors.RESET}"
        
        tags = session.tags or []
        tags_str = ', '.join(tags[:3])
        if len(tags) > 3:
            tags_str += '...'
        
        print(f"{session.name:<30} {len(session.hops):<8} {health_str:<20} {tags_str:<20}")


def cmd_validate(args):
    """Validate a session - check for missing hops and health."""
    # Validate session name to prevent path traversal
    if not validate_session_name(args.session):
        print(f"Error: Invalid session name '{args.session}'. Use alphanumeric characters, underscores, or dashes only.", file=sys.stderr)
        sys.exit(2)
    
    sessions_dir = get_sessions_dir()
    engine = ReplayEngine(sessions_dir)
    
    try:
        session = engine.load_session(args.session)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    
    health = engine.get_session_health(session)
    
    print(f"{Colors.BOLD}Session: {session.name}{Colors.RESET}")
    if 'total_hops' in health:
        print(f"Total hops: {health['total_hops']}")
    print(f"Consecutive hops: {health['consecutive_hops']}")
    print(f"Status: {health['status']}")
    print(f"Message: {health['message']}")
    
    if health['status'] == 'valid':
        sys.exit(0)
    else:
        sys.exit(1)


def cmd_tags(args):
    """Aggregate and display tags across all scenarios."""
    sessions_dir = get_sessions_dir()
    engine = ReplayEngine(sessions_dir)
    sessions = engine.list_sessions()
    
    # Aggregate tags
    tag_counts: dict[str, list[str]] = {}
    for session in sessions:
        for tag in session.tags:
            if tag not in tag_counts:
                tag_counts[tag] = []
            tag_counts[tag].append(session.name)
    
    if not tag_counts:
        print("No tags found.")
        return
    
    print(f"{Colors.BOLD}Tags across all scenarios:{Colors.RESET}\n")
    for tag, session_names in sorted(tag_counts.items()):
        print(f"  {Colors.CYAN}{tag}{Colors.RESET} ({len(session_names)} sessions)")
        for name in session_names:
            print(f"    - {name}")


def cmd_save(args):
    """Save a live capture to a named scenario."""
    # Validate session name to prevent path traversal
    if not validate_session_name(args.name):
        print(f"Error: Invalid session name '{args.name}'. Use alphanumeric characters, underscores, or dashes only.", file=sys.stderr)
        sys.exit(2)
    
    sessions_dir = get_sessions_dir()
    
    # Read from stdin or file with error handling
    if args.file:
        try:
            with open(args.file) as f:
                data = json.load(f)
        except FileNotFoundError as e:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        except (IOError, OSError) as e:
            print(f"Error: Cannot read file: {e}", file=sys.stderr)
            sys.exit(2)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in file: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        # Read from stdin with error handling
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON from stdin: {e}", file=sys.stderr)
            sys.exit(2)
    
    # Create session
    session = Session(
        id=args.name,
        name=args.name,
        data=data,
        tags=args.tags if hasattr(args, 'tags') else []
    )
    
    # Save to file
    session_path = sessions_dir / f"{args.name}.json"
    session.to_file(session_path)
    
    print(f"Saved session '{args.name}' to {session_path}")
    sys.exit(0)


def cmd_viewer(args):
    """Launch the Trace Viewer web interface."""
    from backend.replay.viewer.server import run_viewer
    run_viewer(host=args.host, port=args.port, open_browser=not args.no_browser)


def main():
    """Main entry point for the replay CLI."""
    parser = argparse.ArgumentParser(
        description='Replay Engine CLI - Replay sessions and generate diffs',
        prog='python -m replay'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # run command
    run_parser = subparsers.add_parser('run', help='Replay a session and show diff output')
    run_parser.add_argument('session', help='Session name to replay')
    run_parser.add_argument('--baseline', '-b', help='Baseline session to compare against')
    run_parser.set_defaults(func=cmd_run)
    
    # diff command
    diff_parser = subparsers.add_parser('diff', help='Compare two sessions side by side')
    diff_parser.add_argument('session_a', help='First session')
    diff_parser.add_argument('session_b', help='Second session')
    diff_parser.set_defaults(func=cmd_diff)
    
    # list command
    list_parser = subparsers.add_parser('list', help='List all sessions with hop count and health')
    list_parser.set_defaults(func=cmd_list)
    
    # validate command
    validate_parser = subparsers.add_parser('validate', help='Validate session (check for missing hops)')
    validate_parser.add_argument('session', help='Session to validate')
    validate_parser.set_defaults(func=cmd_validate)
    
    # tags command
    tags_parser = subparsers.add_parser('tags', help='Show all tags across scenarios')
    tags_parser.set_defaults(func=cmd_tags)
    
    # save command
    save_parser = subparsers.add_parser('save', help='Save a live capture as a named scenario')
    save_parser.add_argument('name', help='Name for the scenario')
    save_parser.add_argument('--file', '-f', type=Path, help='Input file (default: stdin)')
    save_parser.add_argument('--tags', '-t', nargs='*', help='Tags to add')
    save_parser.set_defaults(func=cmd_save)
    
    # viewer command
    viewer_parser = subparsers.add_parser('viewer', help='Launch the Trace Viewer web interface')
    viewer_parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    viewer_parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    viewer_parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    viewer_parser.set_defaults(func=cmd_viewer)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
