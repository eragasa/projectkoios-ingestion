# `DiskManagedArtifactByteProvider` schematic

```text
reference + authority + bounds
             |
             v
binding lookup
             |
             v
openat chain with NOFOLLOW
             |
             v
regular file + exact byte ceiling
             |
             v
bounded chunks | translated typed failure
```
