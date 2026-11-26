import sys

f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"

# Read with utf-8-sig to handle BOM, but the bullets are double-encoded so
# we must use the actual strings as they appear in the file
with open(f, encoding='utf-8-sig') as fh:
    content = fh.read()

original_len = len(content)

# The file has mojibake: â€¢ for • and â†' for →
# We use those exact strings in our match patterns

BULLET = '\u00e2\u20ac\u00a2'   # â€¢  (UTF-8 for • double-encoded)
ARROW  = '\u00e2\u2020\u2019'   # â†'  (UTF-8 for → double-encoded)

# Verify
assert BULLET in content, f"BULLET not found: {repr(BULLET)}"
assert ARROW in content, f"ARROW not found: {repr(ARROW)}"
print("Bullet and arrow markers verified")

# ── Change 4: replace the schedules view section ──

OLD4 = (
    "      {!loading && view === 'schedules' && (\n"
    "        <div>\n"
    "          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Reminder Schedules</h2>\n"
    "          {schedules.length === 0 ? (\n"
    "            <div style={{ textAlign: 'center', padding: '40px' }}>\n"
    "              <div style={{ marginBottom: '16px', color: '#6b7280' }}>No schedules configured yet</div>\n"
    "              <button onClick={handleSeedDefaults} style={{\n"
    "                padding: '12px 24px', background: '#3b82f6', color: 'white', border: 'none',\n"
    "                borderRadius: '6px', cursor: 'pointer', fontWeight: 500\n"
    "              }}>\n"
    "                Create Default 4-Step Schedule\n"
    "              </button>\n"
    "            </div>\n"
    "          ) : (\n"
    "            <div style={{ display: 'grid', gap: '16px' }}>\n"
    "              {schedules.map(schedule => (\n"
    "                <div key={schedule.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>\n"
    "                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>\n"
    "                    <div>\n"
    "                      <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{schedule.name}</h3>\n"
    "                      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>\n"
    f"                        {{schedule.step_count}} steps {BULLET} Business hours: {{schedule.send_hour_start}}:00 - {{schedule.send_hour_end}}:00\n"
    "                      </div>\n"
    "                    </div>\n"
    "                    <div style={{\n"
    "                      padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 500,\n"
    "                      background: schedule.enabled ? '#d1fae5' : '#fee2e2',\n"
    "                      color: schedule.enabled ? '#065f46' : '#991b1b'\n"
    "                    }}>\n"
    "                      {schedule.enabled ? 'Active' : 'Disabled'}\n"
    "                    </div>\n"
    "                  </div>\n"
    "                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>\n"
    "                    <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{\n"
    "                    padding: '8px 16px', background: '#f3f4f6', border: 'none',\n"
    "                    borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'\n"
    "                  }}>\n"
    f"                    View Steps {ARROW}\n"
    "                  </button>\n"
    "                    <button onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true) }} style={{\n"
    "                      padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',\n"
    "                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#374151'\n"
    "                    }}>\n"
    "                      Edit\n"
    "                    </button>\n"
    "                  </div>\n"
    "                </div>\n"
    "              ))}\n"
    "            </div>\n"
    "          )}"
)

NEW4 = (
    "      {!loading && view === 'schedules' && (\n"
    "        <div>\n"
    "          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Reminder Schedules</h2>\n"
    "          {schedules.length === 0 ? (\n"
    "            <div style={{ textAlign: 'center', padding: '40px' }}>\n"
    "              <div style={{ marginBottom: '16px', color: '#6b7280' }}>No schedules configured yet</div>\n"
    "              <button onClick={handleSeedDefaults} style={{\n"
    "                padding: '12px 24px', background: '#3b82f6', color: 'white', border: 'none',\n"
    "                borderRadius: '6px', cursor: 'pointer', fontWeight: 500\n"
    "              }}>\n"
    "                Create Default 4-Step Schedule\n"
    "              </button>\n"
    "            </div>\n"
    "          ) : (\n"
    "            <div style={{ display: 'grid', gap: '16px' }}>\n"
    "              {schedules.map(schedule => (\n"
    "                <div key={schedule.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>\n"
    "                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>\n"
    "                    <div style={{ flex: 1 }}>\n"
    "                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>\n"
    "                        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{schedule.name}</h3>\n"
    "                        {schedule.is_default && (\n"
    "                          <span style={{\n"
    "                            padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,\n"
    "                            background: '#dbeafe', color: '#1e40af', textTransform: 'uppercase', letterSpacing: '0.03em'\n"
    "                          }}>\n"
    "                            Default\n"
    "                          </span>\n"
    "                        )}\n"
    "                      </div>\n"
    "                      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>\n"
    f"                        {{schedule.step_count}} steps {BULLET} Business hours: {{schedule.send_hour_start}}:00 - {{schedule.send_hour_end}}:00\n"
    "                      </div>\n"
    "                    </div>\n"
    "                    <div style={{\n"
    "                      padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 500,\n"
    "                      background: schedule.enabled ? '#d1fae5' : '#fee2e2',\n"
    "                      color: schedule.enabled ? '#065f46' : '#991b1b'\n"
    "                    }}>\n"
    "                      {schedule.enabled ? 'Active' : 'Inactive'}\n"
    "                    </div>\n"
    "                  </div>\n"
    "                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>\n"
    "                    <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{\n"
    "                      padding: '8px 16px', background: '#f3f4f6', border: 'none',\n"
    "                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'\n"
    "                    }}>\n"
    f"                      View Steps {ARROW}\n"
    "                    </button>\n"
    "                    <button onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true) }} style={{\n"
    "                      padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',\n"
    "                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#374151',\n"
    "                      display: canManage ? 'inline-flex' : 'none'\n"
    "                    }}>\n"
    "                      Edit\n"
    "                    </button>\n"
    "                    {canManage && (\n"
    "                      <button onClick={() => handleToggle(schedule)} title={schedule.enabled ? 'Deactivate' : 'Activate'} style={{\n"
    "                        padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',\n"
    "                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: schedule.enabled ? '#d97706' : '#059669'\n"
    "                      }}>\n"
    "                        {schedule.enabled ? 'Deactivate' : 'Activate'}\n"
    "                      </button>\n"
    "                    )}\n"
    "                    {canManage && !schedule.is_default && (\n"
    "                      <button onClick={() => handleSetDefault(schedule)} style={{\n"
    "                        padding: '8px 16px', background: 'white', border: '1px solid #3b82f6',\n"
    "                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#3b82f6'\n"
    "                      }}>\n"
    "                        Set as default\n"
    "                      </button>\n"
    "                    )}\n"
    "                    {canManage && (\n"
    '                      <button onClick={() => handleShowArchiveConfirm(schedule)} title="Delete (archive) this schedule" style={{\n'
    "                        padding: '8px 16px', background: 'white', border: '1px solid #dc2626',\n"
    "                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#dc2626'\n"
    "                      }}>\n"
    "                        Delete\n"
    "                      </button>\n"
    "                    )}\n"
    "                  </div>\n"
    "                </div>\n"
    "              ))}\n"
    "            </div>\n"
    "          )}"
)

if OLD4 in content:
    content = content.replace(OLD4, NEW4, 1)
    print("Change 4 OK")
else:
    print("FAIL: Change 4 marker not found")
    # Debug: find index and show surrounding context
    idx = content.find("{schedule.step_count} steps")
    print(f"  Found step_count at index {idx}")
    if idx >= 0:
        print(f"  Bytes: {repr(content[idx:idx+30])}")
    sys.exit(1)

# ── Change 5: insert archive confirmation modal before email preview modal ──

OLD5 = "      {showPreviewModal && previewJob && (() => {"

NEW5 = """\
      {/* Archive Confirmation Dialog */}
      {archiveConfirm && (
        <div
          role="presentation"
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '16px' }}
          onClick={e => { if (e.target === e.currentTarget && !loading) setArchiveConfirm(null) }}
        >
          <div
            role="dialog"
            aria-modal="true"
            style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', boxShadow: '0 20px 60px rgba(0,0,0,0.18)', width: '100%', maxWidth: '480px', padding: '24px' }}
          >
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#dc2626', marginBottom: '16px' }}>
              Delete Schedule "{archiveConfirm.schedule.name}"?
            </h2>
            <p style={{ margin: 0, fontSize: '14px', color: '#374151', lineHeight: 1.6, marginBottom: '12px' }}>
              This schedule will be archived and removed from the list. All existing reminder history will be preserved.
            </p>
            {archiveConfirm.impact.invoices_affected > 0 && (
              <p style={{ margin: 0, fontSize: '14px', color: '#d97706', fontWeight: 500, marginBottom: '12px' }}>
                <strong>{archiveConfirm.impact.invoices_affected} invoice{archiveConfirm.impact.invoices_affected !== 1 ? 's' : ''}</strong> {archiveConfirm.impact.invoices_affected === 1 ? 'is' : 'are'} linked to this schedule. Future reminders for these invoices will fall back to the default schedule.
              </p>
            )}
            {archiveConfirm.impact.live_jobs > 0 && (
              <p style={{ margin: 0, fontSize: '14px', color: '#374151', marginBottom: '12px' }}>
                <strong>{archiveConfirm.impact.live_jobs} pending reminder{archiveConfirm.impact.live_jobs !== 1 ? 's' : ''}</strong> from this schedule will remain visible and can still be approved.
              </p>
            )}
            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setArchiveConfirm(null)} disabled={loading} style={{ flex: 1, padding: '10px 20px', background: 'white', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#374151' }}>
                Cancel
              </button>
              <button onClick={handleArchive} disabled={loading} style={{ flex: 1, padding: '10px 20px', background: '#dc2626', color: 'white', border: 'none', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '14px', fontWeight: 600 }}>
                {loading ? 'Deleting...' : 'Delete Schedule'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showPreviewModal && previewJob && (() => {\
"""

if OLD5 in content:
    content = content.replace(OLD5, NEW5, 1)
    print("Change 5 OK")
else:
    print("FAIL: Change 5 marker not found")
    sys.exit(1)

with open(f, 'w', encoding='utf-8-sig') as fh:
    fh.write(content)

new_len = len(content)
print(f"Done. File size: {original_len} -> {new_len} chars (+{new_len - original_len})")
