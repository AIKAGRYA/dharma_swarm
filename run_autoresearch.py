#!/usr/bin/env python3
"""Autoresearch Loop Runner — Activate Self-Improvement

This script runs the dharma_swarm autoresearch loop continuously,
allowing the system to evolve its own code.

Usage:
    python3 run_autoresearch.py [--dry-run] [--iterations N] [--target module.py]

Examples:
    # Dry run (measure only, no changes)
    python3 run_autoresearch.py --dry-run --iterations 5
    
    # Target specific module
    python3 run_autoresearch.py --target providers.py --iterations 3
    
    # Full run (will propose and apply changes)
    python3 run_autoresearch.py --iterations 10
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add dharma_swarm to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.autoresearch_loop import AutoResearchLoop, LoopConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(REPO_ROOT / "autoresearch.log"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="Run the dharma_swarm autoresearch loop"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Measure fitness only, don't propose changes",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations to run (default: 5)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="",
        help="Target specific module (e.g., 'providers.py')",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=10.0,
        help="Seconds between iterations (default: 10)",
    )
    
    args = parser.parse_args()
    
    # Build config
    target_modules = [args.target] if args.target else []
    config = LoopConfig(
        fitness_threshold=0.6,
        max_iterations=args.iterations,
        sleep_between_sec=args.sleep,
        target_modules=target_modules,
        dry_run=args.dry_run,
    )
    
    logger.info("=" * 60)
    logger.info("AUTORESEARCH LOOP — Activating Self-Improvement")
    logger.info("=" * 60)
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Iterations: {args.iterations}")
    logger.info(f"Target modules: {target_modules or 'ALL'}")
    logger.info(f"Sleep between: {args.sleep}s")
    logger.info("=" * 60)
    
    # Create and run loop
    loop = AutoResearchLoop(config)
    
    try:
        results = await loop.run()
        
        # Print report
        logger.info("\n" + "=" * 60)
        logger.info("FINAL REPORT")
        logger.info("=" * 60)
        print(loop.report())
        
        # Summary
        accepted = sum(1 for r in results if r.accepted)
        logger.info(f"\nSummary: {accepted}/{len(results)} improvements accepted")
        
        if accepted > 0:
            logger.info("🧬 The swarm has evolved itself.")
        else:
            logger.info("📊 Baseline measured. No changes needed (or dry run).")
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user. Progress saved to autoresearch.log")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
