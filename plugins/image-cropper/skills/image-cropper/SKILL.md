---
name: image-cropper
description: Build an image upload field the way Tony does it - pick or drop a file, compress it in the browser with compressorjs (JPEG, max 1024px, EXIF-rotated), then crop it in a dialog with react-easy-crop at a fixed aspect ratio, with zoom that goes below 1 so the whole picture fits (the empty area is filled white), a "fit all" button, a minimum-crop-width quality gate, "edit crop" that re-crops the original instead of the crop, and an optional dual preview (wide + square). Controlled value/onChange string, so it drops into any form library. Use this whenever a project needs an image, photo, logo, avatar, banner, cover, thumbnail or product picture upload, an image cropper, image compression before upload, react-easy-crop, compressorjs, "crop like tony", or "the usual image uploader", even if the user only asks for "an image field" or only one piece (just compression, just the crop helper).
---

# Image cropper, Tony's way

One field, reused across projects: **the user picks or drops a picture, it is
shrunk in the browser, they frame it in a dialog, and the form gets back one
small JPEG at the exact aspect ratio the site shows it at.** The server never
sees a 12 MB phone photo, and no image is ever displayed at a ratio it was not
cropped for.

Read this file, then take the code from [references/code.md](references/code.md):
a framework-free crop helper, a React hook with all the state and handlers, and
a reference component. The hook is the part to keep verbatim; the markup is
meant to be rewritten in the project's own UI kit.

## The decisions, and why

- **Compress first, crop second.** `compressorjs` with `quality: 0.8`,
  `maxWidth/maxHeight: 1024`, `convertSize: 0` (always emit JPEG) and
  `checkOrientation: true` (apply EXIF rotation, so phone photos are not
  sideways). The cropper then works on a ~200 KB image instead of the raw
  file, which keeps the dialog fast on phones and makes the output size
  predictable. Raise `maxWidth` only if the site really shows the image wider
  than 1024 px.
- **Validate before compressing.** Reject non-images and files over the size
  cap (default 10 MB) with a message under the field; do not start work that
  will fail.
- **The value is a string.** A server URL, a `data:` URI, or `''` for no image.
  `onChange` receives the cropped data URI, or `''` on remove. That contract
  works with react-hook-form's `Controller`, Formik, or plain `useState`, and
  lets an existing record's URL show as the preview without special cases.
- **Crop at a fixed aspect: the widest surface it will be shown on.** If the
  same image appears at 16:9 on desktop and 1:1 on mobile, crop at 16:9 and
  turn on the dual preview, which shows the result in both boxes with
  `object-fit: cover`, centered, exactly as the site will. The dialog then tells
  the user to keep the subject in the middle.
- **Zoom can go below 1** (`minZoom` 0.4, `restrictPosition={false}`,
  `objectFit="contain"`). A tall logo in a wide frame can be shrunk until all
  of it fits; the area outside the picture comes out white. A "Fit all"
  button next to the slider jumps to `minZoom`. Without this, users have to
  pre-edit their logo in another app, and they won't.
- **"Edit crop" re-crops the original.** The compressed, uncropped upload is
  kept in state; editing opens the cropper on that, not on the previous crop,
  so repeated edits never lose pixels. It exists only for images uploaded in
  this session; a stored URL can only be replaced.
- **Minimum crop width is a quality gate.** When `minCropWidth` is set and the
  crop area (in source pixels) is narrower, a warning banner shows over the
  cropper and Save is disabled. Zooming in too far on a small photo is the usual
  cause.
- **The crop helper draws, it does not rotate.** A canvas the size of the crop,
  filled white, then `drawImage(img, -x, -y)`. Negative offsets from zooming
  out land in the white. Do not copy the widespread "safe area" snippet that
  paints onto a canvas many times the image size and uses `getImageData`: it
  is slow and goes over browser canvas limits (Safari especially) on large
  images. Add rotation only if the project asks for it.
- **The dialog closes only through Cancel, X, or Save.** Escape is ignored so
  a stray keypress does not throw away framing work; a backdrop click still
  cancels. Full screen below 600 px wide.
- **The dropzone is clickable only when empty.** Once there is an image, the
  preview shows buttons instead: Edit crop, Change, Remove. The file input's
  value is reset after each pick so choosing the same file again still fires.
- **Output is a JPEG data URI.** Upload it the way the project already uploads
  files. If it sends `multipart/form-data` or a presigned PUT, turn it into a
  `Blob` with `dataUrlToBlob()` from the reference rather than switching the
  helper to `toBlob`, so the field's value stays a string.

## Build order

1. **Dependencies.** `react-easy-crop` and `compressorjs`. Known-good:
   `react-easy-crop 5.x`, `compressorjs 1.x`. Both are client-only; in Next.js
   the field file starts with `'use client'`.
2. **Crop helper.** `lib/image/crop-image.ts` (or wherever the project keeps
   browser utils): `cropImage()` and `dataUrlToBlob()` from the reference.
3. **Hook.** `useImageCropper()` next to the component, copied as-is. It owns
   validation, compression, the uncropped original, crop/zoom state, the
   min-width gate and the handlers.
4. **Component.** Write `ImageCropperField` with the project's own Dialog,
   Slider, Button and icon set, following the reference's structure: label,
   dropzone/preview, hidden file input, error line, crop dialog with slider +
   "Fit all", tips, Cancel/Save. Keep the props list; drop the ones the project
   will not use.
5. **Wire it into a form.** With react-hook-form, wrap it in a `Controller`
   (`value={field.value ?? ''}` `onChange={field.onChange}`). Validate on the
   server that the payload is an image and within size; the client check is a
   convenience, not a guard.
6. **Try it.** A large phone photo taken in portrait (EXIF rotation), a
   transparent PNG logo (should come out on white), a very wide banner zoomed
   all the way out, a small image with `minCropWidth` set (Save must disable),
   Edit crop twice in a row (no quality loss), picking the same file twice,
   and the dialog on a phone-width window.

## Adapting to the project

- **UI kit.** The reference markup uses plain elements and inline styles so it
  runs anywhere. Replace them with MUI (`Dialog fullScreen={isMobile}`,
  `Slider`), shadcn/Radix (`Dialog`, `Slider`), Mantine, or whatever is there.
  The cropper box needs `position: relative` and a fixed height (400 px works).
- **Language.** All user-facing copy sits in one `copy` object in the
  reference. Route it through the project's i18n if it has one.
- **Several ratios.** For an avatar, `aspect={1}` and `cropShape="round"` on
  `<Cropper>`; still export a square, and round it with CSS where shown.
- **Transparency must survive.** Only if the project needs it (e.g. logos over
  coloured backgrounds): drop `convertSize: 0`, export `image/png`, and skip
  the white fill. Output gets much bigger; say so.
- **No React.** `cropImage()` and the compression options are framework-free;
  `react-easy-crop` is not. In Vue/Svelte use that ecosystem's cropper and keep
  the same decisions.

## What not to do

- Do not send the original file to the server and crop there "later". The
  point is that the server stores exactly what will be shown.
- Do not let the crop aspect float free. A free-form crop always ends up
  letterboxed or cut off somewhere on the site.
- Do not re-crop the cropped image on edit; keep the uncropped original.
- Do not clamp zoom at 1 or leave `restrictPosition` on; users lose the
  ability to fit a whole logo.
- Do not use the "safe area" canvas crop snippet.
- Do not close the dialog on Escape.
