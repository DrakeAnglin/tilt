#!/bin/sh
# Run one area's tests with line coverage on, for tools/coverage_gate.py:
#   tools/coverage.sh <app|firmware|tools> <out dir>
# Leaves <out dir>/<area>.lcov and the test output <out dir>/<area>.log, and exits with the tests' own status.
#   firmware  tools/firmware_tests.sh (both firmwares), built with clang's coverage by the c++ stand-in in coverage-bin/
#   app       tools/app_tests.sh: the Mac and the iPhone simulator test programs, through the swiftc stand-in, and the
#             Xcode tests (TiltTests, TiltUITests), through the xcodebuild stand-in. One LLVM record per binary: the
#             gate adds up records of the same file, so Shared files count from every run.
#   tools     tools/test_tools.py and tools/agent/test_agent.py under coverage.py (settings: tools/.coveragerc)
# The test scripts are not changed: the stand-ins on PATH add the coverage flags. The plain test runs in CI still say
# pass or fail; this is an extra run of the same tests. For firmware and app, TILT_COVERAGE_TESTS runs another script
# in place of the area's (the tests of this script use it).
set -eu
AREA=${1:?usage: coverage.sh <app|firmware|tools> <out dir>}
OUTDIR=${2:?usage: coverage.sh <app|firmware|tools> <out dir>}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$OUTDIR"
OUTDIR=$(cd "$OUTDIR" && pwd)
W="$OUTDIR/$AREA.work"
rm -rf "$W" "$OUTDIR/$AREA.lcov" "$OUTDIR/$AREA.log"
mkdir -p "$W/bin" "$W/prof"
LOG="$OUTDIR/$AREA.log"

# llvm-cov and llvm-profdata: Xcode's on a Mac, else the plain name, else the newest numbered one (llvm-cov-18).
llvm() {
  if command -v xcrun >/dev/null 2>&1 && xcrun -f "$1" >/dev/null 2>&1; then echo "xcrun $1"; return 0; fi
  if command -v "$1" >/dev/null 2>&1; then echo "$1"; return 0; fi
  N=$(ls /usr/bin/"$1"-[0-9]* 2>/dev/null | sort -t- -k3 -n | tail -1)
  [ -n "$N" ] || { echo "coverage: no $1 (Linux: apt-get install llvm; a Mac: Xcode)" >&2; return 1; }
  echo "$N"
}

# Runs the tests with their output both shown and saved; the exit status goes to $W/rc.
run() { { "$@" 2>&1 || echo $? >"$W/rc"; } | tee -a "$LOG"; }

# The compiled areas: run the tests with the stand-ins first on PATH, then turn the counts into LCOV, one test
# program at a time (the gate adds up records of the same file).
compiled() {
  PROFDATA=$(llvm llvm-profdata)
  COV=$(llvm llvm-cov)
  export TILT_COVERAGE_OUT="$W" TILT_COVERAGE_PATH="$PATH"
  export LLVM_PROFILE_FILE="$W/prof/%p.profraw" SIMCTL_CHILD_LLVM_PROFILE_FILE="$W/prof/%p.profraw"
  PATH="$ROOT/tools/coverage-bin:$PATH" run "$1"
  : >"$OUTDIR/$AREA.lcov"
  if ls "$W"/prof/*.profraw >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    $PROFDATA merge -sparse -o "$W/all.profdata" "$W"/prof/*.profraw
    for B in "$W"/bin/*; do
      [ -f "$B" ] || continue
      # shellcheck disable=SC2086
      $COV export -format=lcov -instr-profile="$W/all.profdata" "$B" >>"$OUTDIR/$AREA.lcov" 2>>"$W/llvm-cov.err" || {
        echo "coverage: llvm-cov could not read $(basename "$B"): $(cat "$W/llvm-cov.err")" >&2
        echo 1 >"$W/rc"
      }
    done
  fi
  # The Xcode tests (app only): Xcode merged their counts itself; one export per binary the xcodebuild stand-in kept.
  if [ -f "$W/xcode/Coverage.profdata" ]; then
    for B in "$W"/xcode/*; do
      [ "$B" = "$W/xcode/Coverage.profdata" ] && continue
      # shellcheck disable=SC2086
      $COV export -format=lcov -instr-profile="$W/xcode/Coverage.profdata" "$B" >>"$OUTDIR/$AREA.lcov" 2>>"$W/llvm-cov.err" || {
        echo "coverage: llvm-cov could not read $(basename "$B"): $(cat "$W/llvm-cov.err")" >&2
        echo 1 >"$W/rc"
      }
    done
  elif ! ls "$W"/prof/*.profraw >/dev/null 2>&1; then
    echo "coverage: no counts were written (did the tests start?)" >&2
  fi
}

case "$AREA" in
  firmware) compiled "${TILT_COVERAGE_TESTS:-$ROOT/tools/firmware_tests.sh}" ;;
  app) compiled "${TILT_COVERAGE_TESTS:-$ROOT/tools/app_tests.sh}" ;;
  tools)
    python3 -c 'import coverage' 2>/dev/null || {
      echo "coverage: the coverage package is missing. Install it: python3 -m pip install --user 'coverage>=7.10'" >&2
      exit 1
    }
    cd "$ROOT"
    export COVERAGE_RCFILE="$ROOT/tools/.coveragerc" COVERAGE_FILE="$W/coverage"
    # The subprocess setting writes its start-up hook into the Python's own site folder; the Mac's Python cannot be
    # written to, so the same hook also goes in a sitecustomize.py on PYTHONPATH (starting twice does nothing).
    mkdir -p "$W/py"
    printf 'import coverage\ncoverage.process_startup()\n' >"$W/py/sitecustomize.py"
    export PYTHONPATH="$W/py${PYTHONPATH:+:$PYTHONPATH}"
    run python3 -m coverage run -m unittest tools/test_tools.py
    run python3 -m coverage run -m unittest tools/agent/test_agent.py
    python3 -m coverage combine -q
    python3 -m coverage lcov -q -o "$OUTDIR/tools.lcov"
    ;;
  *) echo "usage: coverage.sh <app|firmware|tools> <out dir>" >&2; exit 2 ;;
esac
RC=$(cat "$W/rc" 2>/dev/null || echo 0)
[ "$RC" = 0 ] || echo "coverage.sh: the tests exited with status $RC" | tee -a "$LOG" >&2
echo "coverage: $OUTDIR/$AREA.lcov"
exit "$RC"
