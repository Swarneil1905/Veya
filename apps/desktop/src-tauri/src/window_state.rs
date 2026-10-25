//! Small, versioned host-owned preferences; renderer content cannot choose paths.
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tauri::{LogicalSize, PhysicalPosition, WebviewWindow, WindowEvent};

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
struct Saved {
    version: u8,
    x: i32,
    y: i32,
    width: f64,
    height: f64,
    maximized: bool,
}
#[derive(Clone, Copy)]
struct Display {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
    scale: f64,
}

fn fit(saved: Saved, displays: &[Display], frame: (f64, f64)) -> Option<Saved> {
    if saved.version != 1
        || !saved.width.is_finite()
        || !saved.height.is_finite()
        || saved.width <= 0.0
        || saved.height <= 0.0
    {
        return None;
    }
    let valid: Vec<_> = displays
        .iter()
        .filter(|d| d.width > 0 && d.height > 0 && d.scale.is_finite() && d.scale > 0.0)
        .collect();
    let d = valid
        .iter()
        .find(|d| {
            saved.x as i64 >= d.x as i64
                && (saved.x as i64) < d.x as i64 + d.width as i64
                && saved.y as i64 >= d.y as i64
                && (saved.y as i64) < d.y as i64 + d.height as i64
        })
        .copied()
        .or_else(|| valid.first().copied())?;
    let width = saved
        .width
        .max(800.0)
        .min((d.width as f64 / d.scale - frame.0).max(1.0));
    let height = saved
        .height
        .max(640.0)
        .min((d.height as f64 / d.scale - frame.1).max(1.0));
    let max_x = d.x as i64 + d.width as i64 - ((width + frame.0) * d.scale).ceil() as i64;
    let max_y = d.y as i64 + d.height as i64 - ((height + frame.1) * d.scale).ceil() as i64;
    Some(Saved {
        x: (saved.x as i64).clamp(d.x as i64, max_x.max(d.x as i64)) as i32,
        y: (saved.y as i64).clamp(d.y as i64, max_y.max(d.y as i64)) as i32,
        width,
        height,
        ..saved
    })
}
fn read(path: &Path) -> Option<Saved> {
    use std::io::Read;
    let mut data = Vec::new();
    std::fs::File::open(path)
        .ok()?
        .take(4097)
        .read_to_end(&mut data)
        .ok()?;
    if data.len() > 4096 {
        return None;
    }
    serde_json::from_slice(&data).ok()
}
fn snapshot(window: &WebviewWindow) -> Option<Saved> {
    let position = window.outer_position().ok()?;
    let size = window.inner_size().ok()?;
    let scale = window.scale_factor().ok()?;
    Some(Saved {
        version: 1,
        x: position.x,
        y: position.y,
        width: size.width as f64 / scale,
        height: size.height as f64 / scale,
        maximized: window.is_maximized().ok()?,
    })
}
fn save(path: &Path, saved: Saved) -> std::io::Result<()> {
    let data = serde_json::to_vec(&saved)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let temporary = path.with_extension("tmp");
    std::fs::write(&temporary, data)?;
    std::fs::rename(temporary, path)
}
pub fn install(window: &WebviewWindow, path: PathBuf) {
    let displays: Vec<_> = window
        .available_monitors()
        .unwrap_or_default()
        .iter()
        .map(|m| {
            let r = m.work_area();
            Display {
                x: r.position.x,
                y: r.position.y,
                width: r.size.width,
                height: r.size.height,
                scale: m.scale_factor(),
            }
        })
        .collect();
    let frame = match (
        window.outer_size(),
        window.inner_size(),
        window.scale_factor(),
    ) {
        (Ok(outer), Ok(inner), Ok(scale)) if scale > 0.0 => (
            outer.width.saturating_sub(inner.width) as f64 / scale,
            outer.height.saturating_sub(inner.height) as f64 / scale,
        ),
        _ => (16.0, 40.0),
    };
    let restored = read(&path).and_then(|s| fit(s, &displays, frame));
    if let Some(saved) = restored {
        // A smaller work area must still permit all controls to be reached.
        let _ = window.set_min_size(Some(LogicalSize::new(
            saved.width.min(800.0),
            saved.height.min(640.0),
        )));
        let _ = window.set_size(LogicalSize::new(saved.width, saved.height));
        let _ = window.set_position(PhysicalPosition::new(saved.x, saved.y));
        if saved.maximized {
            let _ = window.maximize();
        }
    }
    let normal = Arc::new(Mutex::new(restored.or_else(|| snapshot(window))));
    let owned = window.clone();
    window.on_window_event(move |event| {
        if matches!(event, WindowEvent::Moved(_) | WindowEvent::Resized(_))
            && !owned.is_maximized().unwrap_or(true)
            && !owned.is_minimized().unwrap_or(true)
        {
            if let (Ok(mut state), Some(current)) = (normal.lock(), snapshot(&owned)) {
                *state = Some(current);
            }
        }
        if matches!(event, WindowEvent::CloseRequested { .. }) {
            if let Ok(state) = normal.lock() {
                if let Some(mut saved) = *state {
                    saved.maximized = owned.is_maximized().unwrap_or(false);
                    let _ = save(&path, saved);
                }
            }
        }
    });
}
#[cfg(test)]
mod tests {
    use super::*;
    fn saved() -> Saved {
        Saved {
            version: 1,
            x: 5000,
            y: 3000,
            width: 1440.0,
            height: 1000.0,
            maximized: false,
        }
    }
    #[test]
    fn removed_display_and_scaling_keep_window_reachable() {
        let d = Display {
            x: 0,
            y: 0,
            width: 1920,
            height: 1040,
            scale: 1.5,
        };
        let s = fit(saved(), &[d], (16.0, 40.0)).unwrap();
        assert_eq!((s.x, s.y), (0, 0));
        assert_eq!(s.width, 1264.0);
        assert!((s.height + 40.0) * 1.5 <= 1040.0);
    }
    #[test]
    fn negative_monitor_and_small_work_area_are_supported() {
        let d = Display {
            x: -1280,
            y: -100,
            width: 1280,
            height: 600,
            scale: 1.0,
        };
        let s = fit(
            Saved {
                x: -1200,
                y: 0,
                width: 100.0,
                height: 100.0,
                ..saved()
            },
            &[d],
            (16.0, 40.0),
        )
        .unwrap();
        assert_eq!(s.width, 800.0);
        assert_eq!(s.height, 560.0);
        assert_eq!(s.y, -100);
        assert!(s.x >= -1280 && s.x + s.width as i32 <= 0);
    }
    #[test]
    fn corrupt_or_future_preferences_use_defaults() {
        assert!(fit(
            Saved {
                width: f64::NAN,
                ..saved()
            },
            &[],
            (16.0, 40.0),
        )
        .is_none());
        assert!(fit(
            Saved {
                version: 2,
                ..saved()
            },
            &[],
            (16.0, 40.0),
        )
        .is_none());
        assert!(serde_json::from_slice::<Saved>(b"broken").is_err());
    }
    #[test]
    fn preferences_roundtrip_is_small_and_versioned() {
        let data = serde_json::to_vec(&saved()).unwrap();
        assert!(data.len() < 4096);
        assert_eq!(
            serde_json::from_slice::<Saved>(&data).unwrap().width,
            1440.0
        );
        let mut random = [0u8; 8];
        getrandom::getrandom(&mut random).unwrap();
        let path =
            std::env::temp_dir().join(format!("veya-window-{:x}.json", u64::from_le_bytes(random)));
        save(&path, saved()).unwrap();
        assert_eq!(read(&path).unwrap().width, 1440.0);
        save(
            &path,
            Saved {
                width: 900.0,
                ..saved()
            },
        )
        .unwrap();
        assert_eq!(read(&path).unwrap().width, 900.0);
        std::fs::write(&path, vec![b'x'; 4097]).unwrap();
        assert!(read(&path).is_none());
        std::fs::remove_file(path).unwrap();
    }
}
