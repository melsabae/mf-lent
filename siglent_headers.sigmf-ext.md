# SIGLENT Headers v0.0.1

The `siglent-headers` namespace extension adds the header metadata for SIGLENT binary captures to the SigMF format.

## 1 Global

`siglent-headers` does not extend Global.

## 2 Captures

`siglent-headers` extends Captures.

Each capture is given the header metadata that was parsed from the binary file corresponding to the source of the capture. The extension key is `siglent-headers:<version>:<source>` where source then defines a key-value store of the parsed metadata values. Keys beginning with "_?" are considered placeholders, gaps, or reserved space that the format does not define, and the value associated to any such key is not meaningful.

## 3 Annotations

`siglent-headers` does not extend Annotations.

## 4 Examples

No `siglent-headers` examples.

