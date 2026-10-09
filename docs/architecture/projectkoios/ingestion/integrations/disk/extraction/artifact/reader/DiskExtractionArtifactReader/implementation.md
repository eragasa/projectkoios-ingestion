# `DiskExtractionArtifactReader` implementation

The reader resolves only configured bindings beneath a validated nonsymlink root. It records that root's device/inode identity, walks absolute-root and relative-path components through directory descriptors with `O_NOFOLLOW`, and rejects a replaced root before artifact traversal. It opens the final target nonblocking, requires a regular file, reads in bounded chunks, and rejects size, modification-time, or change-time drift during reading.

Missing or unsafe evidence stops; authority failures request authority; unexpected provider failures permit only an identical retry. The reader returns bytes but performs no extraction decoding or migration decision.
