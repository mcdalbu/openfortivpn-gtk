#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
spec_file="$project_dir/packaging/openfortivpn-gtk.spec"
output_dir="$project_dir/dist"

for tool in rpmbuild rpmspec tar sha256sum; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Ferramenta necessária não encontrada: %s\n' "$tool" >&2
        exit 1
    fi
done

read -r package_name package_version < <(
    rpmspec --query --srpm --queryformat '%{NAME} %{VERSION}\n' "$spec_file"
)
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/openfortivpn-gtk-rpm.XXXXXXXX")"
trap 'rm -rf -- "$build_dir"' EXIT
mkdir -p "$build_dir"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,tmp} "$output_dir"

# Include only application source and packaging assets, excluding local logs
# and Python caches.
tar --create --gzip --file "$build_dir/SOURCES/$package_name-$package_version.tar.gz" \
    --transform "s|^|$package_name-$package_version/|" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --directory "$project_dir" \
    openfortivpn_gtk tests packaging build-rpm.sh README.md LICENSE \
    data/openfortivpn-gtk.desktop data/openfortivpn-gtk.svg data/openfortivpn-gtk.png

rpmbuild -ba --define "_topdir $build_dir" --define "_tmppath $build_dir/tmp" "$spec_file"
cp "$build_dir"/RPMS/noarch/*.rpm "$output_dir/"
cp "$build_dir"/SRPMS/*.src.rpm "$output_dir/"
(
    cd "$output_dir"
    sha256sum "$package_name-$package_version-"*.rpm > SHA256SUMS
)
printf '\nPacotes criados em: %s\n' "$output_dir"
