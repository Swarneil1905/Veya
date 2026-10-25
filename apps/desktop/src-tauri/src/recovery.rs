//! Bounded restart admission, independent of request replay.
use std::collections::VecDeque;
use std::time::{Duration, Instant};

#[derive(Default)]
pub struct Recovery {
    attempts: VecDeque<Instant>,
}
impl Recovery {
    pub fn admit(&mut self, now: Instant) -> bool {
        while self
            .attempts
            .front()
            .is_some_and(|t| now.saturating_duration_since(*t) >= Duration::from_secs(60))
        {
            self.attempts.pop_front();
        }
        if self.attempts.len() >= 2 {
            return false;
        }
        self.attempts.push_back(now);
        true
    }
    pub fn reset(&mut self) {
        self.attempts.clear();
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn restart_storm_is_bounded_and_explicit_retry_resets_it() {
        let mut recovery = Recovery::default();
        let now = Instant::now();
        assert!(recovery.admit(now));
        assert!(recovery.admit(now));
        assert!(!recovery.admit(now));
        assert!(recovery.admit(now + Duration::from_secs(61)));
        recovery.reset();
        assert!(recovery.admit(now));
    }
}
