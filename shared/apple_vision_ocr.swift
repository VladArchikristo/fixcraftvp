import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
if args.count < 2 {
    fputs("Usage: apple_vision_ocr.swift image_path\n", stderr)
    exit(2)
}

let path = args[1]
let url = URL(fileURLWithPath: path)

guard let image = NSImage(contentsOf: url),
      let tiffData = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiffData),
      let cgImage = bitmap.cgImage else {
    fputs("Failed to load image\n", stderr)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["ru-RU", "en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
    let observations = request.results ?? []
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            let text = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                print(text)
            }
        }
    }
} catch {
    fputs("OCR error: \(error)\n", stderr)
    exit(4)
}
