//go:build !windows

package tunnel

// ensureDefenderExclusion is a no-op on non-Windows platforms.
func ensureDefenderExclusion(frpcDataDir string) error {
	return nil
}
