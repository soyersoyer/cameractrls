.PHONY: help deb clean-deb

PACKAGE := $(shell dpkg-parsechangelog -S Source)
VERSION := $(shell dpkg-parsechangelog -S Version)
BUILD_DIR ?= /tmp/$(PACKAGE)-deb-build
OUT_DIR ?= dist/deb

help:
	@echo "Targets:"
	@echo "  make deb       Build Ubuntu/Debian .deb packages into $(OUT_DIR)/"
	@echo "  make clean-deb Remove generated package artifacts in $(OUT_DIR)/"

deb:
	rm -rf "$(BUILD_DIR)"
	mkdir -p "$(BUILD_DIR)" "$(OUT_DIR)"
	rsync -a --delete --exclude ".git/" ./ "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && dpkg-buildpackage -us -uc -b
	find "$(BUILD_DIR)/.." -maxdepth 1 -type f -name "*_$(VERSION)_all.deb" -exec cp -f {} "$(OUT_DIR)/" \;
	find "$(BUILD_DIR)/.." -maxdepth 1 -type f -name "*_$(VERSION)_*.changes" -exec cp -f {} "$(OUT_DIR)/" \;
	find "$(BUILD_DIR)/.." -maxdepth 1 -type f -name "*_$(VERSION)_*.buildinfo" -exec cp -f {} "$(OUT_DIR)/" \;
	@echo "Built packages:"
	@ls -1 "$(OUT_DIR)"/*"_$(VERSION)_all.deb"

clean-deb:
	rm -f "$(OUT_DIR)"/*.deb "$(OUT_DIR)"/*.changes "$(OUT_DIR)"/*.buildinfo
