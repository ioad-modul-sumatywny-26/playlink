#!/usr/bin/env bash
# Użycie: ./build.sh            -> pełny dokument
#         ./build.sh sekcje/X   -> tylko jedna sekcja (test), wynik w build-X/
set -euo pipefail
cd "$(dirname "$0")"
docker image inspect playlink-texlive >/dev/null 2>&1 || docker build -q -t playlink-texlive . >/dev/null
if [[ $# -ge 1 ]]; then
  s=$(basename "${1%.tex}"); out="build-$s"; mkdir -p "$out"
  sed -e '/\\input{sekcje\//d' -e '/\\part{/d' -e '/\\appendix/d' \
      -e "s|\\\\end{document}|\\\\input{sekcje/$s}\n\\\\end{document}|" playlink-kompendium.tex > "$out/test.tex"
  main="$out/test.tex"
else
  out=build; mkdir -p "$out"; main=playlink-kompendium.tex
fi
for i in 1 2; do
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/../..:/w" -w /w/docs/kompendium playlink-texlive \
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$out" "$main" > "$out/log.txt" 2>&1 || { grep -n -A5 '^!' "$out"/*.log | head -40; exit 1; }
done
grep -E "Warning.*(undefined|Overfull \\\\hbox \([3-9][0-9]|multiply)" "$out"/*.log | head -20 || true
echo "OK: $out/$(basename "${main%.tex}").pdf"
