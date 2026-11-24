# Reads a unified diff (a pull request's patch for tools/firmware_tests.sh or tools/app_tests.sh).
# Exits 0 when the change only adds tests: every removed line is a comment, and no added line
# can make a test pass that should fail. Anything else exits 1, and a human decides.
#   awk -f tools/agent/only_adds_tests.awk patch.diff
BEGIN { bad = 0; lines = 0 }
/^(\+\+\+|---)/ { next }                  # file headers
/^@@/ { next }                            # hunk headers
/^-/ {
  lines++
  body = substr($0, 2)
  # A removed line may only be a comment (not the #! line). Removing a command changes how tests run.
  if (body !~ /^[ \t]*#/ || body ~ /^#!/) { bad = 1 }
  next
}
/^\+/ {
  lines++
  body = substr($0, 2)
  if (body ~ /^[ \t]*#/ || body ~ /^[ \t]*$/) { next }
  # Ways to make a failing test look like a pass.
  if (body ~ /\|\|[ \t]*(true|:)([ \t;)]|$)/) { bad = 1 }
  if (body ~ /set[ \t]+\+e/) { bad = 1 }
  if (body ~ /(^|[ \t;&|])exit[ \t]+0([ \t;]|$)/) { bad = 1 }
  # A bare exit passes on the last command's status; only exit with a nonzero number is fine.
  if (body ~ /(^|[ \t;&|])exit([^A-Za-z0-9_]|$)/ && body !~ /(^|[ \t;&|])exit[ \t]+[1-9]/) { bad = 1 }
  if (body ~ /(^|[ \t;&|])exec[ \t]/) { bad = 1 }
  next
}
END { exit (bad || lines == 0) ? 1 : 0 }
