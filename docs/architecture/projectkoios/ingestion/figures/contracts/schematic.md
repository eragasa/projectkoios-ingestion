# `figures.contracts` schematic

```mermaid
classDiagram
    class FigureDetectionConfiguration
    class PageRegionRenderer
    class FigureInspector
    class DeterministicFigureCandidateDetector

    DeterministicFigureCandidateDetector --> FigureDetectionConfiguration
    DeterministicFigureCandidateDetector --> PageRegionRenderer
    DeterministicFigureCandidateDetector --> FigureInspector
```

The facade receives capabilities; it does not compose concrete implementations.
