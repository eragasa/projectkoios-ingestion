# `ingestion.transcript_batch` implementation

The batch composition path imports `PyMuPdfRegionRenderer` from the adapter
module and explicitly injects renderer instances into equation, table, and
figure detectors. Instances retain each consumer's existing aggregate pixel and
raster-byte bounds; they are not hidden behind a factory, registry, global, or
neutral-package default. Transcript processing order and evidence remain
unchanged.
