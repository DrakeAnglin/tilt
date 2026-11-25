# Reads a unified diff (a pull request's patch for tools/firmware_tests.sh or tools/app_tests.sh).
# Exits 0 when the change only adds tests, and 1 otherwise (a human decides).
#   awk -f tools/agent/only_adds_tests.awk patch.diff
#
# An allowlist, not a list of tricks: a removed line may only be a comment, and an added line may only be
#   a comment or blank
#   a compile:     c++ ... / cc ...
#   a test run:    "$OUT/<name>" [args]
#   a generator:   python3 <file>.py [args]
#   the cleanup:   trap 'rm -rf "$OUT"' EXIT
# and none of the commands may hold ; & | ` $( ) { } < > ! (no chaining, no or-else, no subshells,
# no redirects, no functions, no negation). Anything else, even if harmless, goes to a human.
BEGIN { bad = 0; lines = 0; hunk = 0 }
/^@@/ { hunk = 1; next }
!hunk { next }                              # the file headers (--- a/..., +++ b/...) come before the first hunk
/^-/ {
  lines++
  body = substr($0, 2)
  if (body !~ /^[ \t]*#/ || body ~ /^#!/) { bad = 1 }
  next
}
/^\+/ {
  lines++
  body = substr($0, 2)
  if (body ~ /^[ \t]*#/ || body ~ /^[ \t]*$/) { next }
  if (body == "trap 'rm -rf \"$OUT\"' EXIT") { next }
  if (body ~ /[;&|`(){}<>!]/) { bad = 1; next }
  if (body ~ /^(c\+\+|cc)[ \t]/) { next }
  if (body ~ /^"\$OUT\/[A-Za-z0-9_.-]+"([ \t]|$)/) { next }
  if (body ~ /^python3[ \t]+[A-Za-z0-9_.\/-]+\.py([ \t]|$)/) { next }
  bad = 1
  next
}
END { exit (bad || lines == 0) ? 1 : 0 }
