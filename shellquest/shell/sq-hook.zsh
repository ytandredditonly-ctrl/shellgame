# shellquest zsh hook — source this from ~/.zshrc:
#     source /path/to/shellquest/shell/sq-hook.zsh
#
# It reports every executed command (line, exit code, cwd, duration) to the
# game via `sq _hook`. The report is non-blocking: it is backgrounded and
# fully detached, so the shell never waits on it (§10). If `sq` is missing or
# slow, your prompt is unaffected.

# Resolve the `sq` entrypoint once.
if command -v sq >/dev/null 2>&1; then
  _SQ_BIN="sq"
elif [[ -n "${SQ_HOME_DIR:-}" ]]; then
  _SQ_BIN="python3 -m sq"
else
  # Fall back to the package dir two levels up from this file.
  _SQ_DIR="${0:A:h:h}"
  _SQ_BIN="python3 ${_SQ_DIR}/sq"
fi

typeset -g _SQ_START_MS=0
typeset -g _SQ_LAST_CMD=""

_sq_preexec() {
  _SQ_LAST_CMD="$1"
  _SQ_START_MS=$(( EPOCHREALTIME * 1000 ))
}

_sq_precmd() {
  local ec=$?
  [[ -z "$_SQ_LAST_CMD" ]] && return
  local now_ms=$(( EPOCHREALTIME * 1000 ))
  local dur=$(( now_ms - _SQ_START_MS ))
  (( dur < 0 )) && dur=0
  local cmd="$_SQ_LAST_CMD"
  _SQ_LAST_CMD=""
  # Detach completely; stdout/stderr discarded so nothing clutters the prompt.
  ( ${=_SQ_BIN} _hook --cmd "$cmd" --exit "$ec" --cwd "$PWD" --dur "${dur%.*}" \
      >/dev/null 2>&1 & ) >/dev/null 2>&1
}

# zsh/datetime gives EPOCHREALTIME for millisecond timing.
zmodload zsh/datetime 2>/dev/null

autoload -Uz add-zsh-hook
add-zsh-hook preexec _sq_preexec
add-zsh-hook precmd  _sq_precmd

# Optional compact prompt indicator: [L0 ▰▱▱▱▱ 0%].
# Enable by setting SQ_PROMPT=1 before sourcing. Cached-cheap but still a
# subprocess per prompt, so it is opt-in.
if [[ "${SQ_PROMPT:-0}" == "1" ]]; then
  setopt prompt_subst
  _sq_ind() { ${=_SQ_BIN} _prompt 2>/dev/null }
  PROMPT='$(_sq_ind) '"$PROMPT"
fi
