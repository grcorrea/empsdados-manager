# Fonts

This directory should contain the following WOFF2 font files for optimal rendering:

## Required Fonts

| Font | File | Source |
|------|------|--------|
| Inter Regular | `Inter-Regular.woff2` | [Google Fonts](https://fonts.google.com/specimen/Inter) |
| Inter Medium | `Inter-Medium.woff2` | [Google Fonts](https://fonts.google.com/specimen/Inter) |
| Inter SemiBold | `Inter-SemiBold.woff2` | [Google Fonts](https://fonts.google.com/specimen/Inter) |
| Poppins Regular | `Poppins-Regular.woff2` | [Google Fonts](https://fonts.google.com/specimen/Poppins) |
| Poppins SemiBold | `Poppins-SemiBold.woff2` | [Google Fonts](https://fonts.google.com/specimen/Poppins) |
| Roboto Regular | `Roboto-Regular.woff2` | [Google Fonts](https://fonts.google.com/specimen/Roboto) |
| Roboto Medium | `Roboto-Medium.woff2` | [Google Fonts](https://fonts.google.com/specimen/Roboto) |

## Fallback Behavior

If fonts are not present, the system will fall back to:
- **Inter** → system sans-serif
- **Poppins** → system sans-serif
- **Roboto** → system sans-serif

## Download Script

```bash
# Download fonts from Google Fonts API
curl -o Inter-Regular.woff2 "https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2"
curl -o Inter-Medium.woff2 "https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa2JL7.woff2"
curl -o Inter-SemiBold.woff2 "https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa25L7.woff2"
```

Fonts are optional but recommended for brand-accurate rendering.
