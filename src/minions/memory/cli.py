#!/usr/bin/env python3
"""
Memory CLI - Command-line interface for Memory Broker.

Usage:
    memory add "content" --type preference --context "user correction"
    memory search "keyword" --limit 5
    memory list --type preference --limit 10
    memory stats
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure src is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from minions.memory import (
    AgentType,
    MemoryScope,
    MemoryType,
    get_broker,
)


def cmd_add(args: argparse.Namespace) -> int:
    """Add a memory."""
    broker = get_broker(enable_mem0=args.mem0)

    # Parse enums
    memory_type = MemoryType(args.type)
    scope = MemoryScope(args.scope)
    agent = AgentType(args.agent)

    # Parse tags
    tags = args.tags.split(",") if args.tags else []

    event = broker.add(
        content=args.content,
        memory_type=memory_type,
        scope=scope,
        source_agent=agent,
        context=args.context or "",
        tags=tags,
    )

    if args.json:
        print(json.dumps(event.to_dict(), ensure_ascii=False))
    else:
        print(f"✓ Memory saved: {event.id[:8]}...")

    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search memories."""
    broker = get_broker(enable_mem0=args.mem0)

    # Parse optional filters
    scope = MemoryScope(args.scope) if args.scope else None
    memory_type = MemoryType(args.type) if args.type else None
    agent = AgentType(args.agent) if args.agent else None

    results = broker.search(
        query=args.query,
        scope=scope,
        memory_type=memory_type,
        source_agent=agent,
        limit=args.limit,
        use_semantic=args.mem0,
    )

    if args.json:
        print(json.dumps([e.to_dict() for e in results], ensure_ascii=False))
    else:
        if not results:
            print("No memories found.")
            return 0

        for event in results:
            print(f"\n[{event.memory_type.value}] {event.content[:100]}")
            if event.context:
                print(f"  Context: {event.context}")
            print(f"  ID: {event.id[:8]}... | {event.created_at[:10]}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List recent memories."""
    broker = get_broker(enable_mem0=False)  # No semantic search for list

    # Use empty query for listing
    results = broker.search(
        query="",
        memory_type=MemoryType(args.type) if args.type else None,
        source_agent=AgentType(args.agent) if args.agent else None,
        limit=args.limit,
        use_semantic=False,
    )

    if args.json:
        print(json.dumps([e.to_dict() for e in results], ensure_ascii=False))
    else:
        if not results:
            print("No memories found.")
            return 0

        for event in results:
            type_str = f"[{event.memory_type.value}]".ljust(14)
            content_preview = event.content[:60].replace("\n", " ")
            print(f"{type_str} {content_preview}")

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show memory statistics."""
    broker = get_broker(enable_mem0=args.mem0)
    stats = broker.get_stats()

    if args.json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        print(f"Total memories: {stats['total_events']}")
        print(f"Session memories: {stats['session_events']}")
        print(f"Sessions: {stats['session_count']}")
        print(f"mem0 enabled: {stats['mem0_enabled']}")
        print("\nBy type:")
        for t, count in stats.get("by_type", {}).items():
            print(f"  {t}: {count}")
        print("\nBy agent:")
        for a, count in stats.get("by_agent", {}).items():
            print(f"  {a}: {count}")

    return 0


def cmd_relevant(args: argparse.Namespace) -> int:
    """Get relevant memories for current context (for session start)."""
    broker = get_broker(enable_mem0=args.mem0)

    # Search for preferences and workflows
    memories = []

    # Get user preferences
    prefs = broker.search(
        query="",
        memory_type=MemoryType.PREFERENCE,
        scope=MemoryScope.USER,
        limit=5,
        use_semantic=False,
    )
    memories.extend(prefs)

    # Get workflows
    workflows = broker.search(
        query="",
        memory_type=MemoryType.WORKFLOW,
        scope=MemoryScope.USER,
        limit=3,
        use_semantic=False,
    )
    memories.extend(workflows)

    # Get recent errors (for context)
    errors = broker.search(
        query="",
        memory_type=MemoryType.ERROR,
        limit=3,
        use_semantic=False,
    )
    memories.extend(errors)

    # Dedupe by content
    seen = set()
    unique = []
    for m in memories:
        if m.content not in seen:
            seen.add(m.content)
            unique.append(m)

    if args.json:
        print(json.dumps([e.to_dict() for e in unique], ensure_ascii=False))
    else:
        if not unique:
            print("No relevant memories.")
            return 0

        print("# Relevant Memories\n")
        for event in unique:
            print(f"- [{event.memory_type.value}] {event.content}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Memory CLI for Multi-Agent Orchestra",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--mem0", action="store_true", help="Enable mem0 semantic search"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    add_parser = subparsers.add_parser("add", help="Add a memory")
    add_parser.add_argument("content", help="Memory content")
    add_parser.add_argument(
        "--type",
        "-t",
        default="preference",
        choices=[t.value for t in MemoryType],
        help="Memory type",
    )
    add_parser.add_argument(
        "--scope",
        "-s",
        default="user",
        choices=[s.value for s in MemoryScope],
        help="Memory scope",
    )
    add_parser.add_argument(
        "--agent",
        "-a",
        default="claude",
        choices=[a.value for a in AgentType],
        help="Source agent",
    )
    add_parser.add_argument(
        "--context",
        "-c",
        help="Additional context",
    )
    add_parser.add_argument(
        "--tags",
        help="Comma-separated tags",
    )
    add_parser.set_defaults(func=cmd_add)

    # search command
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--type",
        "-t",
        choices=[t.value for t in MemoryType],
        help="Filter by type",
    )
    search_parser.add_argument(
        "--scope",
        "-s",
        choices=[s.value for s in MemoryScope],
        help="Filter by scope",
    )
    search_parser.add_argument(
        "--agent",
        "-a",
        choices=[a.value for a in AgentType],
        help="Filter by agent",
    )
    search_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Max results",
    )
    search_parser.set_defaults(func=cmd_search)

    # list command
    list_parser = subparsers.add_parser("list", help="List recent memories")
    list_parser.add_argument(
        "--type",
        "-t",
        choices=[t.value for t in MemoryType],
        help="Filter by type",
    )
    list_parser.add_argument(
        "--agent",
        "-a",
        choices=[a.value for a in AgentType],
        help="Filter by agent",
    )
    list_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Max results",
    )
    list_parser.set_defaults(func=cmd_list)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # relevant command (for session start)
    relevant_parser = subparsers.add_parser(
        "relevant",
        help="Get relevant memories for session",
    )
    relevant_parser.set_defaults(func=cmd_relevant)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
