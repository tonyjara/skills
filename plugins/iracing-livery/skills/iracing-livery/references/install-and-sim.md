# Files, folders and seeing it in the sim

## Names and folders

Every file carries the driver's iRacing customer ID (a number on their account page). Below
it is `123456`, a placeholder: use the real one. All files are 24-bit RLE TGAs at their
template's size.

```
Documents\iRacing\paint\<car folder>\car_123456.tga         the car
Documents\iRacing\paint\<car folder>\car_spec_123456.tga    its finish (optional)
Documents\iRacing\paint\helmet_123456.tga                   the helmet, in every car
Documents\iRacing\paint\suit_123456.tga                     the suit, in every car
```

- `<car folder>` is the car's own short name, created the first time the car is loaded.
  For example, `mx5 mx52016` is the Global Mazda MX-5 Cup. Trading Paints' car list shows
  the same names.
- A helmet or suit in the root `paint` folder is the default in every car. A copy inside a
  car's folder is worn in that car only.
- Kits that share file names overwrite each other: install one direction at a time. When
  switching to a kit without a spec map, delete the old `car_spec_` file (see
  spec-maps.md).

## Seeing it, and reloading

1. Copy the files, then open the car in iRacing's 3D car viewer, or start a Test Drive in
   that car.
2. After replacing a TGA, press **Ctrl+R** in the sim. The car flashes and shows the new
   paint. A car sitting in its pit stall doesn't reload, so drive out of the stall first.
3. When handing files over, name exactly which files changed and where each one goes. A
   fix to the car alone means copying `car_` again, plus `car_spec_` if the graphics moved.
   Helmets and suits are separate.

## The race number

The sim draws the number itself, inside the template's **Number Blocks**, in colours and
a font the driver picks in iRacing's paint shop.

- Leave those blocks to it. Give each one a plain, light, solid panel with a margin (or a
  dark one with a light number), with no pattern behind it. A race official, a broadcast
  and other drivers must read the number at a glance.
- Don't make a custom number file (`car_num_<id>.tga`). A custom number is only shown to
  viewers who turn off the sim's own numbers, and that switch hides every other car's
  numbers for them too. For one car, it isn't worth it.

## What the sim adds on top

- **The template's mandatory layer:** maker logos, model badges, plates, black trim on the
  car, and the inner shell (`helmet_decal`) on the helmet. Your paint is underneath, so
  plan around these.
- **The licence colour** on both ends of the helmet's sunstrip.
- **iRacing's sponsor decals:** custom paints don't get them, so nothing covers your
  lettering.

## Who sees it

Files in `Documents\iRacing\paint` are seen only on that PC. Other drivers see the paint
only through **Trading Paints**:
- make a free account linked to the iRacing account;
- upload the car TGA to that car, and the helmet and suit to their slots (some extras, such
  as spec maps, may need the paid tier: the upload page says which);
- keep the Trading Paints Downloader running while racing.

Other drivers see it only if they run the Downloader too. Most people in official series
do. In the paint shop, also set a built-in pattern in the brand's colours, as the fallback
for everyone who doesn't.
