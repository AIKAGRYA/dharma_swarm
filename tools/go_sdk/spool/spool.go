// Package spool provides a file-native, idempotent receipt spool.
//
// Boundary: the spool stores and replays Go SDK receipts only. It does not
// decide, dispatch, write runtime state, write ontology state, or claim
// transport liveness. Consumers own projection, policy, and delivery authority.
package spool

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

// State is the delivery lifecycle for a spooled receipt.
type State string

const (
	StatePending     State = "pending"
	StateDelivered   State = "delivered"
	StateFailed      State = "failed"
	StateQuarantined State = "quarantined"
)

// Entry stores delivery metadata outside the receipt payload.
type Entry struct {
	SpoolID       string          `json:"spool_id"`
	State         State           `json:"state"`
	AttemptCount  int             `json:"attempt_count"`
	FirstSeenAt   string          `json:"first_seen_at"`
	LastAttemptAt *string         `json:"last_attempt_at"`
	LastError     *string         `json:"last_error"`
	Consumer      string          `json:"consumer"`
	Receipt       receipt.Receipt `json:"receipt"`
}

// EntryError reports a bad spool entry without blocking valid entries.
type EntryError struct {
	Path  string `json:"path"`
	Error string `json:"error"`
}

// ListResult is returned by List.
type ListResult struct {
	Entries []Entry      `json:"entries"`
	Errors  []EntryError `json:"errors"`
}

// ReplayResult describes one replay attempt over pending entries.
type ReplayResult struct {
	Delivered []Entry      `json:"delivered"`
	Failed    []Entry      `json:"failed"`
	Skipped   []Entry      `json:"skipped"`
	Errors    []EntryError `json:"errors"`
}

// Append stores receipt r once, keyed by receipt_id. If the entry already
// exists, the stored entry is returned unchanged.
func Append(dir string, r receipt.Receipt, consumer string) (Entry, error) {
	if err := validateReceipt(r); err != nil {
		return Entry{}, err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return Entry{}, err
	}
	path := entryPath(dir, r.ReceiptID)
	if existing, err := readEntry(path); err == nil {
		return existing, nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return Entry{}, err
	}
	entry := Entry{
		SpoolID:      r.ReceiptID,
		State:        StatePending,
		AttemptCount: 0,
		FirstSeenAt:  utcNow(),
		Consumer:     consumer,
		Receipt:      r,
	}
	if err := writeEntry(path, entry); err != nil {
		return Entry{}, err
	}
	return entry, nil
}

// List returns valid entries, sorted by first_seen_at then spool_id. Corrupt
// entries are reported in result.Errors and do not block valid entries.
func List(dir string, states ...State) (ListResult, error) {
	result := ListResult{}
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		return result, nil
	}
	if err != nil {
		return result, err
	}
	allowed := stateSet(states)
	for _, item := range entries {
		if item.IsDir() || !strings.HasSuffix(item.Name(), ".json") {
			continue
		}
		path := filepath.Join(dir, item.Name())
		entry, err := readEntry(path)
		if err != nil {
			result.Errors = append(result.Errors, EntryError{Path: path, Error: err.Error()})
			continue
		}
		if len(allowed) == 0 || allowed[entry.State] {
			result.Entries = append(result.Entries, entry)
		}
	}
	sort.Slice(result.Entries, func(i, j int) bool {
		if result.Entries[i].FirstSeenAt == result.Entries[j].FirstSeenAt {
			return result.Entries[i].SpoolID < result.Entries[j].SpoolID
		}
		return result.Entries[i].FirstSeenAt < result.Entries[j].FirstSeenAt
	})
	return result, nil
}

// MarkDelivered marks a spooled receipt delivered for consumer.
func MarkDelivered(dir, spoolID, consumer string) (Entry, error) {
	return mark(dir, spoolID, consumer, StateDelivered, "")
}

// MarkFailed marks a spooled receipt failed and records lastError.
func MarkFailed(dir, spoolID, consumer, lastError string) (Entry, error) {
	if lastError == "" {
		return Entry{}, errors.New("last_error is required")
	}
	return mark(dir, spoolID, consumer, StateFailed, lastError)
}

// MarkQuarantined marks a spooled receipt quarantined and records lastError.
func MarkQuarantined(dir, spoolID, consumer, lastError string) (Entry, error) {
	if lastError == "" {
		return Entry{}, errors.New("last_error is required")
	}
	return mark(dir, spoolID, consumer, StateQuarantined, lastError)
}

// ReplayPending delivers pending entries for consumer. Successful deliveries
// are marked delivered. Failed deliveries are marked failed with the returned
// error. Running ReplayPending again is idempotent for delivered entries.
func ReplayPending(dir, consumer string, deliver func(Entry) error) (ReplayResult, error) {
	if deliver == nil {
		return ReplayResult{}, errors.New("deliver callback is required")
	}
	list, err := List(dir, StatePending)
	if err != nil {
		return ReplayResult{}, err
	}
	result := ReplayResult{Errors: list.Errors}
	for _, entry := range list.Entries {
		if consumer != "" && entry.Consumer != "" && entry.Consumer != consumer {
			result.Skipped = append(result.Skipped, entry)
			continue
		}
		attempted, err := incrementAttempt(dir, entry.SpoolID, consumer)
		if err != nil {
			result.Errors = append(result.Errors, EntryError{Path: entryPath(dir, entry.SpoolID), Error: err.Error()})
			continue
		}
		if err := deliver(attempted); err != nil {
			failed, markErr := MarkFailed(dir, attempted.SpoolID, consumer, err.Error())
			if markErr != nil {
				result.Errors = append(result.Errors, EntryError{Path: entryPath(dir, attempted.SpoolID), Error: markErr.Error()})
				continue
			}
			result.Failed = append(result.Failed, failed)
			continue
		}
		delivered, err := MarkDelivered(dir, attempted.SpoolID, consumer)
		if err != nil {
			result.Errors = append(result.Errors, EntryError{Path: entryPath(dir, attempted.SpoolID), Error: err.Error()})
			continue
		}
		result.Delivered = append(result.Delivered, delivered)
	}
	return result, nil
}

func mark(dir, spoolID, consumer string, state State, lastError string) (Entry, error) {
	entry, err := readEntry(entryPath(dir, spoolID))
	if err != nil {
		return Entry{}, err
	}
	if err := validateConsumer(entry, consumer); err != nil {
		return Entry{}, err
	}
	entry.State = state
	if consumer != "" {
		entry.Consumer = consumer
	}
	if lastError == "" {
		entry.LastError = nil
	} else {
		entry.LastError = stringPtr(lastError)
	}
	if err := writeEntry(entryPath(dir, spoolID), entry); err != nil {
		return Entry{}, err
	}
	return entry, nil
}

func incrementAttempt(dir, spoolID, consumer string) (Entry, error) {
	entry, err := readEntry(entryPath(dir, spoolID))
	if err != nil {
		return Entry{}, err
	}
	if err := validateConsumer(entry, consumer); err != nil {
		return Entry{}, err
	}
	entry.AttemptCount++
	now := utcNow()
	entry.LastAttemptAt = &now
	if consumer != "" {
		entry.Consumer = consumer
	}
	if err := writeEntry(entryPath(dir, spoolID), entry); err != nil {
		return Entry{}, err
	}
	return entry, nil
}

func validateReceipt(r receipt.Receipt) error {
	if r.ReceiptID == "" {
		return errors.New("receipt_id is required")
	}
	if r.EventUID == "" {
		return errors.New("event_uid is required")
	}
	return nil
}

func validateConsumer(entry Entry, consumer string) error {
	if consumer == "" || entry.Consumer == "" || entry.Consumer == consumer {
		return nil
	}
	return fmt.Errorf("consumer mismatch: entry has %q, got %q", entry.Consumer, consumer)
}

func readEntry(path string) (Entry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Entry{}, err
	}
	var entry Entry
	if err := json.Unmarshal(data, &entry); err != nil {
		return Entry{}, err
	}
	if entry.SpoolID == "" {
		return Entry{}, errors.New("spool_id is required")
	}
	if entry.State == "" {
		return Entry{}, errors.New("state is required")
	}
	if entry.Receipt.ReceiptID == "" {
		return Entry{}, errors.New("receipt.receipt_id is required")
	}
	return entry, nil
}

func writeEntry(path string, entry Entry) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(entry, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	tmp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

func entryPath(dir, spoolID string) string {
	return filepath.Join(dir, safeName(spoolID)+".json")
}

func safeName(value string) string {
	var b strings.Builder
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' || r == '.' {
			b.WriteRune(r)
			continue
		}
		b.WriteByte('_')
	}
	return b.String()
}

func stateSet(states []State) map[State]bool {
	if len(states) == 0 {
		return nil
	}
	set := make(map[State]bool, len(states))
	for _, state := range states {
		set[state] = true
	}
	return set
}

func utcNow() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func stringPtr(value string) *string {
	return &value
}
