---
title: Sensor enclosure optics, depth validity and raked front panels
tags: camera, sensor, raked panel, field view, 시야, 카메라, 센서, 역경사, 간섭
authority: internal_guide
source: https://www.realsenseai.com/products/real-sense-depth-camera-d455f/
checked: 2026-10-21
applicability: Vendor page is titled D455; URL contains d455f, so confirm exact purchased variant and datasheet revision
summary: Quantify optical envelope, panel projection and usable depth separately; no coverage percentage without a defined experiment.
---

# Sensor enclosure design

## D455 source scope
The vendor page describes a 124 x 26 x 29 mm body, depth FOV 87 x 58 degrees,
ideal range 0.6-6 m and approximate minimum depth distance 0.52 m at maximum
resolution. Verify the installed variant, resolution, calibration and mounting
drawing before using these catalogue values in detail design. Rotating the body
can exchange horizontal/vertical angular extents, but does not automatically
establish calibrated coverage or stereo performance.

Source: [RealSense product page](https://www.realsenseai.com/products/real-sense-depth-camera-d455f/),
accessed 2026-10-21. These are short factual catalogue notes; not a CAD measurement.

## Reproducible side-section equations
Frame X forward, Z up; camera optical center (0,h), down pitch p from horizontal,
vertical FOV v. On a flat unobstructed ground plane:

- lower ray angle = p + v/2; near horizontal distance = h / tan(p+v/2).
- upper ray angle = p - v/2; far distance = h / tan(p-v/2) only when upper ray points down.
- when upper ray is horizontal/up, far ground bound is unbounded in this optical
  slice model, not infinite usable sensor range.
- slant range = sqrt(h² + x²). Check the relevant vendor minimum-depth definition;
  the built-in calculator uses an explicit conservative slant bound and does not
  claim it implements every sensor's axial-Z depth limit.

For a panel of height H raked a from vertical, forward edge shift = H tan(a).
For a camera box length L along the panel and depth D normal to it, full X extent
= L sin(a) + D cos(a). This is not the tip motion about a center pivot or the
distance protruding from a shell. Always name the reference surfaces.

## Sensor acceptance experiment
Define scene domain, camera extrinsics/intrinsics, lens centers, body geometry,
joint poses, tessellation/ray tolerance, spatial sample size and depth validity.
Record visible-sample count/total eligible samples and a convergence check at a
finer grid. Evaluate front/rear/side occlusion, stereo baseline, IR emitter and
USB bend/service volume. No body-collision result proves optical visibility.
AR glass needs wavelength/transmission, reflection and contamination testing;
covering an active-stereo camera with arbitrary tinted glass is unverified.
