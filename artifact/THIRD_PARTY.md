# Third-party obligations

Project userspace C/Python code is MIT; BPF source declares GPL-2.0 to use tracing helpers. Kernel-exported types and generated headers follow their upstream notices. Build dependencies are not relicensed by this repository.

libbpf1.5.1 is dual-licensed LGPL-2.1/BSD-2-Clause: preserve upstream `LICENSE`, `LICENSE.BSD-2-Clause`, `LICENSE.LGPL-2.1` in any redistributed vendored build. The bootstrap keeps downloaded source and licenses in the project dependency prefix; the release inventory must include notices if bundling libbpf binaries.

Python dependency licenses (including transitive wheels) are supplied in their installed distribution metadata. Record wheel hashes with `python -m pip download -r requirements-analysis.lock --dest artifact/wheels` on the actual target,then inventory them before an offline release. Do not claim a cross-platform wheel hash lock from a version-only file.

Context coursework and literature documents are preserved as supplied; their inclusion is not a grant to republish third-party papers. Release local artifacts to the user; public publication requires separate authorization.
