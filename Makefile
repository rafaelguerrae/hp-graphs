# ============================================================
# hp-graphs Makefile
# Comunicação e Redes — college project
# ============================================================

# Virtual-environment directory (never committed)
VENV    := .venv
PYTHON  := $(VENV)/bin/python3
PIP     := $(VENV)/bin/pip

SRC     := src
OUT     := output

# Pre-defined snapshot filenames (match extract.py auto-naming)
SNAPSHOT_ALL   := $(OUT)/hpd_graph_all_top40_minco2.json
SNAPSHOT_EARLY := $(OUT)/hpd_graph_Book1-Book2_top40_minco2.json
SNAPSHOT_MID   := $(OUT)/hpd_graph_Book3-Book4-Book5_top40_minco2.json
SNAPSHOT_LATE  := $(OUT)/hpd_graph_Book6-Book7_top40_minco2.json

.PHONY: help install setup extract extract-all extract-periods \
        view view-all view-early view-mid view-late \
        all clean venv

# ------------------------------------------------------------
# Default target: show help
# ------------------------------------------------------------
help:
	@echo ""
	@echo "  hp-graphs — available commands"
	@echo "  ──────────────────────────────────────────────────────────────"
	@echo "  make install            Create venv + install dependencies"
	@echo ""
	@echo "  make extract            Extract full-series graph (all books, top 40)"
	@echo "  make extract-periods    Extract early / mid / late snapshots"
	@echo ""
	@echo "  make view               Render full-series graph → output/"
	@echo "  make view-early         Render Books 1-2 graph"
	@echo "  make view-mid           Render Books 3-5 graph"
	@echo "  make view-late          Render Books 6-7 graph"
	@echo "  make view-all           Render all four graphs"
	@echo ""
	@echo "  make all                Full pipeline: extract + render everything"
	@echo "  make clean              Remove generated output files"
	@echo "  make clean-venv         Remove the virtual environment"
	@echo "  ──────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  Custom book filter (use with extract or view targets):"
	@echo "    make extract BOOKS='Book1 Book2'    → any combination"
	@echo "    make extract BOOKS='Book3'          → single book"
	@echo "    make view    BOOKS='Book1 Book2'    → render that snapshot"
	@echo ""
	@echo "  Other extract options:"
	@echo "    make extract TOP=30 MINCO=3"
	@echo "  ──────────────────────────────────────────────────────────────"
	@echo ""

# ------------------------------------------------------------
# Venv / install
# Creates .venv on first run; subsequent calls are instant.
# ------------------------------------------------------------
$(VENV)/bin/python3:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt

install setup: $(VENV)/bin/python3
	@echo "✓ Virtual environment ready at $(VENV)/"

# ------------------------------------------------------------
# Extract — build graph JSON files
#
# Override any option from the command line, e.g.:
#   make extract BOOKS='Book1 Book2' TOP=30 MINCO=3
# ------------------------------------------------------------

# Defaults (overridable)
BOOKS :=
TOP   := 40
MINCO := 2

# Build the --books flag only when BOOKS is set
_BOOKS_FLAG := $(if $(BOOKS),--books $(BOOKS),)

# Build the auto-generated filename the same way extract.py does
_SCOPE := $(if $(BOOKS),$(subst $(eval) ,-,$(sort $(BOOKS))),all)
_FNAME := hpd_graph_$(_SCOPE)_top$(TOP)$(if $(filter-out 1,$(MINCO)),_minco$(MINCO),).json

extract extract-all: $(VENV)/bin/python3
	$(PYTHON) $(SRC)/extract.py $(_BOOKS_FLAG) --top-chars $(TOP) --min-cooccur $(MINCO)

extract-periods: $(VENV)/bin/python3 $(SNAPSHOT_EARLY) $(SNAPSHOT_MID) $(SNAPSHOT_LATE)

$(SNAPSHOT_ALL): $(VENV)/bin/python3
	$(PYTHON) $(SRC)/extract.py --top-chars 40 --min-cooccur 2

$(SNAPSHOT_EARLY): $(VENV)/bin/python3
	$(PYTHON) $(SRC)/extract.py --books Book1 Book2 --top-chars 40 --min-cooccur 2

$(SNAPSHOT_MID): $(VENV)/bin/python3
	$(PYTHON) $(SRC)/extract.py --books Book3 Book4 Book5 --top-chars 40 --min-cooccur 2

$(SNAPSHOT_LATE): $(VENV)/bin/python3
	$(PYTHON) $(SRC)/extract.py --books Book6 Book7 --top-chars 40 --min-cooccur 2

# ------------------------------------------------------------
# View — render PNG graphs
# ------------------------------------------------------------

view: $(VENV)/bin/python3
	$(PYTHON) $(SRC)/view.py \
		--snapshot $(OUT)/$(if $(BOOKS),$(_FNAME),hpd_graph_all_top$(TOP)$(if $(filter-out 1,$(MINCO)),_minco$(MINCO),).json) \
		--out $(OUT)/hpd_graph_snapshot_$(if $(BOOKS),$(_SCOPE),all).png

view-early: $(SNAPSHOT_EARLY) $(VENV)/bin/python3
	$(PYTHON) $(SRC)/view.py \
		--snapshot $(SNAPSHOT_EARLY) \
		--out $(OUT)/hpd_graph_snapshot_early.png

view-mid: $(SNAPSHOT_MID) $(VENV)/bin/python3
	$(PYTHON) $(SRC)/view.py \
		--snapshot $(SNAPSHOT_MID) \
		--out $(OUT)/hpd_graph_snapshot_mid.png

view-late: $(SNAPSHOT_LATE) $(VENV)/bin/python3
	$(PYTHON) $(SRC)/view.py \
		--snapshot $(SNAPSHOT_LATE) \
		--out $(OUT)/hpd_graph_snapshot_late.png

view-all: view view-early view-mid view-late

# ------------------------------------------------------------
# Full pipeline
# ------------------------------------------------------------
all: install extract-all extract-periods view-all

# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------
clean:
	rm -f $(OUT)/hpd_graph_*.json $(OUT)/hpd_graph_*.png
	@echo "output/ cleaned."

clean-venv:
	rm -rf $(VENV)
	@echo ".venv removed."
