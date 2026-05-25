"""
Run all three MCP servers concurrently in a single process.

Usage:
  python -m mcp_servers.run_all
  python -m mcp_servers.run_all --no-search   # skip Search server
  python -m mcp_servers.run_all --no-car-data # skip Car Data server
  python -m mcp_servers.run_all --no-rag      # skip RAG server
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Run all MCP servers")
    parser.add_argument("--no-search", action="store_true", help="Skip Search server")
    parser.add_argument("--no-car-data", action="store_true", help="Skip Car Data server")
    parser.add_argument("--no-rag", action="store_true", help="Skip RAG server")
    parser.add_argument("--base-port", type=int, default=9100, help="Base port (search=9100, car-data=9101, rag=9102)")
    args = parser.parse_args()

    threads = []
    base = args.base_port

    if not args.no_search:
        from mcp_servers.search_server import SearchMCPServer
        search = SearchMCPServer(port=base)
        t = threading.Thread(target=search.run, name="search-mcp", daemon=True)
        threads.append(t)
        print(f"[run_all] Search MCP Server → http://127.0.0.1:{base}")

    if not args.no_car_data:
        from mcp_servers.car_data_server import CarDataMCPServer
        car_data = CarDataMCPServer(port=base + 1)
        t = threading.Thread(target=car_data.run, name="car-data-mcp", daemon=True)
        threads.append(t)
        print(f"[run_all] Car Data MCP Server → http://127.0.0.1:{base + 1}")

    if not args.no_rag:
        from mcp_servers.rag_server import RAGVectorMCPServer
        rag = RAGVectorMCPServer(port=base + 2)
        t = threading.Thread(target=rag.run, name="rag-vector-mcp", daemon=True)
        threads.append(t)
        print(f"[run_all] RAG Vector MCP Server → http://127.0.0.1:{base + 2}")

    if not threads:
        print("[run_all] No servers selected. Use flags to enable at least one.")
        return

    print(f"\n[run_all] Started {len(threads)} MCP server(s). Press Ctrl+C to stop.\n")

    for t in threads:
        t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[run_all] Shutting down all MCP servers...")


if __name__ == "__main__":
    main()
