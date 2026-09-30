# Image cropper: reference code

Three files. Paths are suggestions; put them where the project keeps things.

1. `lib/image/crop-image.ts`: framework-free canvas helpers.
2. `components/image-cropper/useImageCropper.ts`: all state and behaviour. Copy as-is.
3. `components/image-cropper/ImageCropperField.tsx`: the markup. Plain elements
   and inline styles so it runs anywhere; **rewrite it with the project's UI kit**
   (Dialog, Slider, Button, icons) and keep the structure.

Dependencies: `react-easy-crop` (5.x) and `compressorjs` (1.x).

---

## 1. `lib/image/crop-image.ts`

```ts
export interface PixelArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CropImageOptions {
  /** Fills whatever the crop area covers outside the picture (zoomed out). */
  background?: string;
  type?: 'image/jpeg' | 'image/png' | 'image/webp';
  quality?: number;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    // Remote URLs need CORS or the canvas becomes tainted and toDataURL throws.
    if (!src.startsWith('data:') && !src.startsWith('blob:')) img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/**
 * Crops `src` to `area` (source-image pixels, as react-easy-crop's
 * `croppedAreaPixels` reports them). The area may extend past the image
 * when the user zoomed out below 1; that part comes out as `background`.
 */
export async function cropImage(
  src: string,
  area: PixelArea,
  { background = '#ffffff', type = 'image/jpeg', quality = 0.9 }: CropImageOptions = {},
): Promise<string> {
  const img = await loadImage(src);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(area.width);
  canvas.height = Math.round(area.height);

  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context unavailable');

  if (type !== 'image/png') {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  ctx.drawImage(img, -Math.round(area.x), -Math.round(area.y));

  return canvas.toDataURL(type, quality);
}

/** For multipart uploads / presigned PUTs; the field's value stays a string. */
export function dataUrlToBlob(dataUrl: string): Blob {
  const [header, base64] = dataUrl.split(',');
  const mime = header.match(/data:(.*?);/)?.[1] ?? 'application/octet-stream';
  const bytes = atob(base64);
  const buf = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
  return new Blob([buf], { type: mime });
}
```

---

## 2. `components/image-cropper/useImageCropper.ts`

```ts
'use client';

import { useCallback, useRef, useState } from 'react';
import type { Area, Point } from 'react-easy-crop';
import Compressor from 'compressorjs';
import { cropImage } from '@/lib/image/crop-image';

export const DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
/* Below 1 lets wide/tall images shrink until the whole subject fits the frame
 * (the exposed area is filled white on export). */
export const DEFAULT_MIN_ZOOM = 0.4;
export const DEFAULT_MAX_ZOOM = 4;

/* Shrink before cropping: fast cropper on phones, predictable output size. */
const COMPRESS_OPTIONS: Compressor.Options = {
  quality: 0.8,
  maxWidth: 1024,
  maxHeight: 1024,
  convertSize: 0, // always emit JPEG
  checkOrientation: true, // apply EXIF rotation
};

export const defaultCopy = {
  unsupported: 'Unsupported format. Use JPG, PNG or WebP.',
  tooLarge: (mb: number) => `The image is larger than ${mb} MB.`,
  readError: 'Could not read the image.',
  processError: 'Could not process the image.',
  cropError: 'Could not crop the image.',
};

export interface UseImageCropperOptions {
  onChange: (value: string) => void;
  minCropWidth?: number;
  maxFileSize?: number;
  minZoom?: number;
  copy?: typeof defaultCopy;
}

export function useImageCropper({
  onChange,
  minCropWidth,
  maxFileSize = DEFAULT_MAX_FILE_SIZE,
  minZoom = DEFAULT_MIN_ZOOM,
  copy = defaultCopy,
}: UseImageCropperOptions) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  /** What the cropper is showing right now. */
  const [source, setSource] = useState<string | undefined>();
  /** The compressed, uncropped upload, so "Edit crop" re-crops the original. */
  const [original, setOriginal] = useState<string | null>(null);
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [areaPixels, setAreaPixels] = useState<Area | null>(null);

  const tooSmall = Boolean(minCropWidth && areaPixels && areaPixels.width < minCropWidth);

  const openCropper = useCallback((src: string, isFreshUpload: boolean) => {
    setSource(src);
    if (isFreshUpload) setOriginal(src);
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setAreaPixels(null);
    setDialogOpen(true);
  }, []);

  /* Validate → compress → read → open cropper */
  const handleFile = useCallback(
    (file: File) => {
      setError('');
      if (!file.type.startsWith('image/')) return setError(copy.unsupported);
      if (file.size > maxFileSize) return setError(copy.tooLarge(Math.round(maxFileSize / 1024 / 1024)));

      setLoading(true);
      new Compressor(file, {
        ...COMPRESS_OPTIONS,
        success(result) {
          const reader = new FileReader();
          reader.onload = () => {
            openCropper(reader.result as string, true);
            setLoading(false);
          };
          reader.onerror = () => {
            setError(copy.readError);
            setLoading(false);
          };
          reader.readAsDataURL(result);
        },
        error(err) {
          setError(err.message || copy.processError);
          setLoading(false);
        },
      });
    },
    [copy, maxFileSize, openCropper],
  );

  const onCropComplete = useCallback((_area: Area, pixels: Area) => setAreaPixels(pixels), []);

  const save = useCallback(async () => {
    if (!source || !areaPixels || tooSmall) return;
    try {
      onChange(await cropImage(source, areaPixels));
      setDialogOpen(false);
    } catch (e) {
      console.error(e);
      setError(copy.cropError);
    }
  }, [source, areaPixels, tooSmall, onChange, copy]);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = ''; // allow re-selecting the same file
  };

  const onDrop = (e: React.DragEvent, disabled?: boolean) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return {
    inputRef,
    loading,
    error,
    dragOver,
    setDragOver,
    dialogOpen,
    source,
    canEditCrop: Boolean(original),
    crop,
    setCrop,
    zoom,
    setZoom,
    tooSmall,
    onCropComplete,
    onInputChange,
    onDrop,
    openPicker: () => inputRef.current?.click(),
    editCrop: () => original && openCropper(original, false),
    fitAll: () => setZoom(minZoom),
    remove: () => {
      onChange('');
      setOriginal(null);
      setError('');
    },
    closeDialog: () => setDialogOpen(false),
    save,
  };
}
```

---

## 3. `components/image-cropper/ImageCropperField.tsx`

Reference markup. Swap every element for the project's UI kit equivalent.
Keep: dropzone clickable only when empty, preview + Edit/Change/Remove when
filled, overlay closes on backdrop click but **not** on Escape, full screen on
narrow screens, "Fit all" beside the slider, Save disabled while `tooSmall`.

```tsx
'use client';

import Cropper from 'react-easy-crop';
import {
  DEFAULT_MAX_FILE_SIZE,
  DEFAULT_MAX_ZOOM,
  DEFAULT_MIN_ZOOM,
  defaultCopy,
  useImageCropper,
} from './useImageCropper';

const ACCEPTED_TYPES = 'image/jpeg,image/png,image/webp';

const copy = {
  ...defaultCopy,
  dropTitle: 'Drag an image here or click to upload',
  hint: (mb: number) => `JPG, PNG or WebP · max ${mb} MB`,
  processing: 'Processing image…',
  empty: 'No image',
  editCrop: 'Edit crop',
  change: 'Change image',
  remove: 'Remove',
  dialogTitle: 'Adjust image',
  fitAll: 'Fit all',
  tooSmall: (w: number) => `Image too small: the crop must be at least ${w} px wide.`,
  tips: [
    'Use the slider (or "Fit all") to zoom out until the whole image fits; zoom in to crop.',
    'Leave some space between the edges and the main subject.',
  ],
  dualTip: 'This image is shown both wide and square: keep the subject centered.',
  desktop: 'Desktop preview',
  mobile: 'Mobile preview',
  cancel: 'Cancel',
  save: 'Save image',
};

export interface ImageCropperFieldProps {
  /** A server URL, a data URI, or '' when empty. */
  value: string;
  /** Receives the cropped JPEG data URI, or '' when removed. */
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Crop ratio: the widest surface the image is shown on. Default 16/9. */
  aspect?: number;
  /** Also preview the crop as a centered square (for wide-on-desktop, square-on-mobile). */
  dualPreview?: boolean;
  label?: string;
  /** Reject crops narrower than this many source pixels. */
  minCropWidth?: number;
  minZoom?: number;
  maxZoom?: number;
  maxFileSize?: number;
  accept?: string;
}

/* Fill, center and cover a position:relative parent: how the site shows it. */
const coverImg: React.CSSProperties = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  objectPosition: 'center',
};

function PreviewBox({ src, aspect, width, caption }: { src: string; aspect: string; width: number; caption?: string }) {
  return (
    <figure style={{ margin: 0, display: 'grid', gap: 6, justifyItems: 'center' }}>
      {caption && <figcaption style={{ fontSize: 12, fontWeight: 600, opacity: 0.7 }}>{caption}</figcaption>}
      <div
        style={{
          position: 'relative',
          overflow: 'hidden',
          width,
          maxWidth: '100%',
          aspectRatio: aspect,
          borderRadius: 6,
          border: '1px solid #ddd',
        }}
      >
        <img src={src} alt={caption ?? 'Preview'} style={coverImg} />
      </div>
    </figure>
  );
}

export default function ImageCropperField({
  value,
  onChange,
  disabled = false,
  aspect = 16 / 9,
  dualPreview = false,
  label,
  minCropWidth,
  minZoom = DEFAULT_MIN_ZOOM,
  maxZoom = DEFAULT_MAX_ZOOM,
  maxFileSize = DEFAULT_MAX_FILE_SIZE,
  accept = ACCEPTED_TYPES,
}: ImageCropperFieldProps) {
  const c = useImageCropper({ onChange, minCropWidth, maxFileSize, minZoom, copy });
  const hasImage = Boolean(value);
  const maxMb = Math.round(maxFileSize / 1024 / 1024);

  return (
    <div>
      {label && <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>}

      {/* Dropzone / preview */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) c.setDragOver(true);
        }}
        onDragLeave={() => c.setDragOver(false)}
        onDrop={(e) => c.onDrop(e, disabled)}
        onClick={() => !disabled && !hasImage && !c.loading && c.openPicker()}
        style={{
          border: `1px dashed ${c.dragOver ? 'currentColor' : '#ccc'}`,
          borderRadius: 6,
          padding: 16,
          display: 'grid',
          gap: 12,
          justifyItems: 'center',
          cursor: disabled || hasImage ? 'default' : 'pointer',
        }}
      >
        {c.loading ? (
          <p>{copy.processing}</p>
        ) : hasImage ? (
          <>
            {dualPreview ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, justifyContent: 'center' }}>
                <PreviewBox src={value} aspect="16/9" width={330} caption={copy.desktop} />
                <PreviewBox src={value} aspect="1/1" width={158} caption={copy.mobile} />
              </div>
            ) : (
              <PreviewBox src={value} aspect={`${aspect}`} width={320} />
            )}
            {!disabled && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                {c.canEditCrop && (
                  <button type="button" onClick={c.editCrop}>
                    {copy.editCrop}
                  </button>
                )}
                <button type="button" onClick={c.openPicker}>
                  {copy.change}
                </button>
                <button type="button" onClick={c.remove}>
                  {copy.remove}
                </button>
              </div>
            )}
          </>
        ) : disabled ? (
          <p>{copy.empty}</p>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0 }}>{copy.dropTitle}</p>
            <small>{copy.hint(maxMb)}</small>
          </div>
        )}
      </div>

      <input ref={c.inputRef} type="file" accept={accept} onChange={c.onInputChange} hidden />
      {c.error && <p style={{ color: 'crimson', fontSize: 12, marginTop: 6 }}>{c.error}</p>}

      {/* Crop dialog: backdrop click cancels, Escape deliberately does nothing. */}
      {c.dialogOpen && (
        <div
          onClick={c.closeDialog}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'grid', placeItems: 'center', zIndex: 1000 }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={copy.dialogTitle}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              width: 'min(900px, 100vw)',
              maxHeight: '100dvh',
              overflow: 'auto',
              borderRadius: 8,
              // On phones make this full screen (MUI: fullScreen={useMediaQuery('(max-width:600px)')}).
            }}
          >
            <header style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 16px' }}>
              <strong>{copy.dialogTitle}</strong>
              <button type="button" onClick={c.closeDialog} aria-label={copy.cancel}>
                ✕
              </button>
            </header>

            <div style={{ position: 'relative' }}>
              {c.tooSmall && minCropWidth && (
                <div style={{ position: 'absolute', top: 0, insetInline: 0, zIndex: 10, padding: 16, background: '#ffe08a', fontWeight: 600 }}>
                  {copy.tooSmall(minCropWidth)}
                </div>
              )}
              <div style={{ position: 'relative', width: '100%', height: 400 }}>
                <Cropper
                  image={c.source}
                  crop={c.crop}
                  zoom={c.zoom}
                  minZoom={minZoom}
                  maxZoom={maxZoom}
                  aspect={aspect}
                  restrictPosition={false}
                  objectFit="contain"
                  onCropChange={c.setCrop}
                  onZoomChange={c.setZoom}
                  onCropComplete={c.onCropComplete}
                />
              </div>
            </div>

            <footer style={{ display: 'grid', gap: 16, padding: 16 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <button type="button" onClick={c.fitAll}>
                  {copy.fitAll}
                </button>
                <input
                  type="range"
                  aria-label="Zoom"
                  min={minZoom}
                  max={maxZoom}
                  step={0.01}
                  value={c.zoom}
                  onChange={(e) => c.setZoom(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
              </div>
              <ol style={{ margin: 0, paddingInlineStart: 20, fontSize: 14 }}>
                {copy.tips.map((t) => (
                  <li key={t}>{t}</li>
                ))}
                {dualPreview && <li>{copy.dualTip}</li>}
              </ol>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button type="button" onClick={c.closeDialog}>
                  {copy.cancel}
                </button>
                <button type="button" disabled={c.tooSmall} onClick={c.save}>
                  {copy.save}
                </button>
              </div>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Wiring examples

react-hook-form:

```tsx
<Controller
  control={control}
  name="coverImage"
  render={({ field }) => (
    <ImageCropperField
      label="Cover"
      value={field.value ?? ''}
      onChange={field.onChange}
      aspect={16 / 9}
      dualPreview
      minCropWidth={600}
    />
  )}
/>
```

Plain state, uploading as a file:

```tsx
const [logo, setLogo] = useState('');
// on submit:
const body = new FormData();
if (logo.startsWith('data:')) body.append('logo', dataUrlToBlob(logo), 'logo.jpg');
```

A value that is still a URL means "unchanged"; send nothing for it.
