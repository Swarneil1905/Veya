//! Opaque W3C trace identity for native requests. No UI strings enter headers.
pub fn parent() -> Result<String, String> {
    let mut bytes = [0u8; 24];
    getrandom::getrandom(&mut bytes).map_err(|_| "trace_unavailable".to_string())?;
    let hex: String = bytes.iter().map(|v| format!("{v:02x}")).collect();
    Ok(format!("00-{}-{}-01", &hex[..32], &hex[32..]))
}

#[cfg(test)]
mod tests {
    #[test]
    fn correlation_is_unique_and_bounded() {
        let a = super::parent().unwrap();
        assert_eq!(a.len(), 55);
        assert_ne!(a, super::parent().unwrap());
        assert!(a.starts_with("00-"));
    }
}
