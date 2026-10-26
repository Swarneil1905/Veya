//! Ephemeral file selection grants. Paths never cross IPC and there is no path-read command.
use base64::Engine;
use serde::Serialize;
use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::Read;
use std::path::{Path, PathBuf};

const MAX_BYTES: u64 = 524_288;
#[derive(Serialize)]
pub struct SelectedFile {
    name: String,
    content: Option<String>,
    error: Option<String>,
}
struct Selection {
    paths: HashSet<PathBuf>,
}
fn plain_path(path: &Path) -> Result<PathBuf, String> {
    if !path.is_absolute() {
        return Err("Select an absolute file path".into());
    }
    for ancestor in path.ancestors() {
        let meta = fs::symlink_metadata(ancestor).map_err(|_| "File is unavailable")?;
        if meta.file_type().is_symlink() {
            return Err("Linked files and folders are not supported".into());
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if meta.file_attributes() & 0x400 != 0 {
                return Err("Linked files and folders are not supported".into());
            }
        }
    }
    path.canonicalize()
        .map_err(|_| "File is unavailable".into())
}
impl Selection {
    fn read(&self, path: &Path) -> Result<Vec<u8>, String> {
        let canonical = plain_path(path)?;
        if !self.paths.contains(&canonical) {
            return Err("File is outside this selection".into());
        }
        let mut options = OpenOptions::new();
        options.read(true);
        #[cfg(windows)]
        {
            use std::os::windows::fs::OpenOptionsExt;
            // Deny write/delete sharing during the snapshot and don't follow final reparse points.
            options.share_mode(1).custom_flags(0x00200000);
        }
        let file: File = options
            .open(&canonical)
            .map_err(|_| "File could not be opened")?;
        let meta = file.metadata().map_err(|_| "File is unavailable")?;
        if !meta.is_file() || meta.len() == 0 || meta.len() > MAX_BYTES {
            return Err("Choose a nonempty document up to 512 KiB".into());
        }
        if plain_path(path)? != canonical {
            return Err("File changed during selection".into());
        }
        let mut bytes = Vec::new();
        file.take(MAX_BYTES + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| "File could not be read")?;
        if bytes.len() as u64 > MAX_BYTES {
            return Err("Document exceeds 512 KiB".into());
        }
        Ok(bytes)
    }
}
fn snapshots(paths: Vec<PathBuf>) -> Result<Vec<SelectedFile>, String> {
    if paths.len() > 10 {
        return Err("Choose at most 10 documents".into());
    }
    let mut selected = Selection {
        paths: HashSet::new(),
    };
    let mut output = Vec::new();
    for path in paths {
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("Unnamed document")
            .to_string();
        let result = plain_path(&path).and_then(|canonical| {
            selected.paths.insert(canonical.clone());
            let result = selected.read(&canonical);
            selected.paths.remove(&canonical); // Grant ends immediately after the immutable snapshot.
            result
        });
        output.push(match result {
            Ok(bytes) => SelectedFile {
                name,
                content: Some(base64::engine::general_purpose::STANDARD.encode(bytes)),
                error: None,
            },
            Err(error) => SelectedFile {
                name,
                content: None,
                error: Some(error),
            },
        });
    }
    Ok(output)
}
#[cfg(windows)]
pub fn pick(folder: bool) -> Result<Vec<SelectedFile>, String> {
    let picker = rfd::FileDialog::new().set_title("Select documents for Veya");
    let paths = if folder {
        let Some(folder) = picker.pick_folder() else {
            return Ok(Vec::new());
        };
        let folder = plain_path(&folder)?;
        let mut paths = Vec::new();
        for (index, entry) in fs::read_dir(folder)
            .map_err(|_| "Folder could not be opened")?
            .take(1001)
            .enumerate()
        {
            if index == 1000 {
                return Err("Folder contains too many entries; select files individually".into());
            }
            let entry = entry.map_err(|_| "Folder entry could not be read")?;
            // Top-level documents only, never recursive or parent-drive access.
            let path = entry.path();
            if path
                .extension()
                .and_then(|x| x.to_str())
                .is_some_and(|x| ["pdf", "csv", "xlsx", "eml"].contains(&x.to_lowercase().as_str()))
            {
                paths.push(path);
            }
            if paths.len() > 10 {
                return Err(
                    "Folder contains more than 10 documents; select files individually".into(),
                );
            }
        }
        paths.sort();
        paths
    } else {
        picker
            .add_filter("Documents", &["pdf", "csv", "xlsx", "eml"])
            .pick_files()
            .unwrap_or_default()
    };
    snapshots(paths)
}
#[cfg(not(windows))]
pub fn pick(_folder: bool) -> Result<Vec<SelectedFile>, String> {
    snapshots(Vec::new())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn selection_denies_siblings_and_revoked_paths() {
        let root = std::env::temp_dir().join(format!("veya-files-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let a = root.join("a.csv");
        let b = root.join("b.csv");
        fs::write(&a, b"a,b").unwrap();
        fs::write(&b, b"c,d").unwrap();
        let a = plain_path(&a).unwrap();
        let b = plain_path(&b).unwrap();
        let mut selection = Selection {
            paths: HashSet::from([a.clone()]),
        };
        assert_eq!(selection.read(&a).unwrap(), b"a,b");
        assert!(selection.read(&b).is_err());
        selection.paths.clear();
        assert!(selection.read(&a).is_err());
        let copied = snapshots(vec![a.clone()]).unwrap();
        assert!(copied[0].content.is_some());
        fs::remove_file(a).unwrap();
        fs::remove_file(b).unwrap();
        fs::remove_dir(root).unwrap();
    }
    #[test]
    fn selection_bounds_counts_and_paths() {
        assert!(snapshots(vec![PathBuf::from("relative"); 11]).is_err());
        assert!(plain_path(Path::new("../secret")).is_err());
    }
}
