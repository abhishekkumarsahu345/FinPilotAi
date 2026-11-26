import sys

f = r"c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend\src\App.tsx"

with open(f, encoding='utf-8') as fh:
    content = fh.read()

original_len = len(content)

# ── Change 3: insert handler functions before "// Initial load" useEffect ──

OLD3 = "  }, [org.id])\n\n  // Initial load\n  useEffect(() => {\n    loadSchedules()\n    if (view === 'pending') loadJobs('proposed')"

NEW3 = """\
  }, [org.id])

  // Check if user can manage schedules (owner or manager)
  const canManage = org.role === 'owner' || org.role === 'manager'

  // Toggle schedule active/inactive
  const handleToggle = async (schedule: ReminderSchedule) => {
    if (!canManage) {
      setError('Only Business Owner or Finance Manager can toggle schedules.')
      return
    }

    // If deactivating the default, show a confirmation
    if (schedule.enabled && schedule.is_default) {
      if (!confirm(`"${schedule.name}" is the default schedule. Set another schedule as default before deactivating it.`)) return
      setError('This is the default schedule. Set another schedule as default before deactivating it.')
      return
    }

    // Show confirmation when deactivating
    if (schedule.enabled) {
      if (!confirm(`Deactivate "${schedule.name}"? New reminders will not be created from this schedule while it's inactive. Pending approvals and already-sent reminders are not affected.`)) return
    }

    setLoading(true)
    setError('')
    try {
      const updated = await api.toggleSchedule(org.id, schedule.id)
      setSchedules(prev => prev.map(s => s.id === updated.id ? updated : s))
      setSuccess(`Schedule "${updated.name}" ${updated.enabled ? 'activated' : 'deactivated'}.`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to toggle schedule')
    } finally {
      setLoading(false)
    }
  }

  // Show archive confirmation dialog
  const handleShowArchiveConfirm = async (schedule: ReminderSchedule) => {
    if (!canManage) {
      setError('Only Business Owner or Finance Manager can delete schedules.')
      return
    }
    if (schedule.is_default) {
      setError('This is the default schedule. Set another schedule as default before deleting it.')
      return
    }
    setLoading(true)
    try {
      const impact = await api.archiveImpact(org.id, schedule.id)
      setArchiveConfirm({ schedule, impact })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load schedule impact')
    } finally {
      setLoading(false)
    }
  }

  // Archive schedule
  const handleArchive = async () => {
    if (!archiveConfirm) return
    const { schedule } = archiveConfirm
    setLoading(true)
    setError('')
    try {
      const result = await api.archiveSchedule(org.id, schedule.id)
      setSchedules(prev => prev.filter(s => s.id !== schedule.id))
      setArchiveConfirm(null)
      setSuccess(result.detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to archive schedule')
    } finally {
      setLoading(false)
    }
  }

  // Set schedule as default
  const handleSetDefault = async (schedule: ReminderSchedule) => {
    if (!canManage) {
      setError('Only Business Owner or Finance Manager can change the default schedule.')
      return
    }
    if (schedule.is_default) return
    setLoading(true)
    setError('')
    try {
      const updated = await api.setDefaultSchedule(org.id, schedule.id)
      setSchedules(prev => prev.map(s => s.id === updated.id ? { ...s, is_default: true } : { ...s, is_default: false }))
      setSuccess(`"${updated.name}" set as the default reminder schedule.`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to set default schedule')
    } finally {
      setLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    loadSchedules()
    if (view === 'pending') loadJobs('proposed')\
"""

if OLD3 in content:
    content = content.replace(OLD3, NEW3, 1)
    print("Change 3 OK")
else:
    print("FAIL: Change 3 marker not found")
    sys.exit(1)

# ── Change 4: replace the schedules view section ──

OLD4 = """\
      {!loading && view === 'schedules' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Reminder Schedules</h2>
          {schedules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ marginBottom: '16px', color: '#6b7280' }}>No schedules configured yet</div>
              <button onClick={handleSeedDefaults} style={{
                padding: '12px 24px', background: '#3b82f6', color: 'white', border: 'none',
                borderRadius: '6px', cursor: 'pointer', fontWeight: 500
              }}>
                Create Default 4-Step Schedule
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {schedules.map(schedule => (
                <div key={schedule.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{schedule.name}</h3>
                      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                        {schedule.step_count} steps \u2022 Business hours: {schedule.send_hour_start}:00 - {schedule.send_hour_end}:00
                      </div>
                    </div>
                    <div style={{
                      padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 500,
                      background: schedule.enabled ? '#d1fae5' : '#fee2e2',
                      color: schedule.enabled ? '#065f46' : '#991b1b'
                    }}>
                      {schedule.enabled ? 'Active' : 'Disabled'}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{
                    padding: '8px 16px', background: '#f3f4f6', border: 'none',
                    borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'
                  }}>
                    View Steps \u2192
                  </button>
                    <button onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true) }} style={{
                      padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',
                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#374151'
                    }}>
                      Edit
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Schedule Steps Panel */}
          {selectedSchedule && (
            <div style={{ marginTop: '24px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Steps for: {selectedSchedule.name}</h3>
                <button onClick={() => setSelectedSchedule(null)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280'
                }}>
                  <X size={20} />
                </button>
              </div>
              {steps.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#6b7280' }}>No steps configured</div>
              ) : (
                <div style={{ display: 'grid', gap: '12px' }}>
                  {steps.map(step => (
                    <div key={step.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                            Step {step.step_number}: {step.tone_display}
                          </div>
                          <div style={{ fontSize: '13px', color: '#6b7280' }}>
                            Trigger: {step.offset_from_due !== null
                              ? `${step.offset_from_due} days ${step.offset_from_due < 0 ? 'before' : 'after'} due date`
                              : `${step.offset_from_issue} days from invoice issue`}
                          </div>
                          <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                            Approval: {step.approval_mode_display}
                            {step.is_final_notice && <span style={{ marginLeft: '8px', color: '#dc2626', fontWeight: 500 }}>(Final Notice)</span>}
                          </div>
                        </div>
                        <div style={{
                          padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
                          background: step.enabled ? '#d1fae5' : '#fee2e2',
                          color: step.enabled ? '#065f46' : '#991b1b'
                        }}>
                          {step.enabled ? 'Enabled' : 'Disabled'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}"""

NEW4 = """\
      {!loading && view === 'schedules' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Reminder Schedules</h2>
          {schedules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ marginBottom: '16px', color: '#6b7280' }}>No schedules configured yet</div>
              <button onClick={handleSeedDefaults} style={{
                padding: '12px 24px', background: '#3b82f6', color: 'white', border: 'none',
                borderRadius: '6px', cursor: 'pointer', fontWeight: 500
              }}>
                Create Default 4-Step Schedule
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {schedules.map(schedule => (
                <div key={schedule.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{schedule.name}</h3>
                        {schedule.is_default && (
                          <span style={{
                            padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,
                            background: '#dbeafe', color: '#1e40af', textTransform: 'uppercase', letterSpacing: '0.03em'
                          }}>
                            Default
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                        {schedule.step_count} steps \u2022 Business hours: {schedule.send_hour_start}:00 - {schedule.send_hour_end}:00
                      </div>
                    </div>
                    <div style={{
                      padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 500,
                      background: schedule.enabled ? '#d1fae5' : '#fee2e2',
                      color: schedule.enabled ? '#065f46' : '#991b1b'
                    }}>
                      {schedule.enabled ? 'Active' : 'Inactive'}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{
                      padding: '8px 16px', background: '#f3f4f6', border: 'none',
                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'
                    }}>
                      View Steps \u2192
                    </button>
                    <button onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true) }} style={{
                      padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',
                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#374151',
                      display: canManage ? 'inline-flex' : 'none'
                    }}>
                      Edit
                    </button>
                    {canManage && (
                      <button onClick={() => handleToggle(schedule)} title={schedule.enabled ? 'Deactivate' : 'Activate'} style={{
                        padding: '8px 16px', background: 'white', border: '1px solid #d1d5db',
                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: schedule.enabled ? '#d97706' : '#059669'
                      }}>
                        {schedule.enabled ? 'Deactivate' : 'Activate'}
                      </button>
                    )}
                    {canManage && !schedule.is_default && (
                      <button onClick={() => handleSetDefault(schedule)} style={{
                        padding: '8px 16px', background: 'white', border: '1px solid #3b82f6',
                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#3b82f6'
                      }}>
                        Set as default
                      </button>
                    )}
                    {canManage && (
                      <button onClick={() => handleShowArchiveConfirm(schedule)} title="Delete (archive) this schedule" style={{
                        padding: '8px 16px', background: 'white', border: '1px solid #dc2626',
                        borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', color: '#dc2626'
                      }}>
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Schedule Steps Panel */}
          {selectedSchedule && (
            <div style={{ marginTop: '24px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Steps for: {selectedSchedule.name}</h3>
                <button onClick={() => setSelectedSchedule(null)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280'
                }}>
                  <X size={20} />
                </button>
              </div>
              {steps.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#6b7280' }}>No steps configured</div>
              ) : (
                <div style={{ display: 'grid', gap: '12px' }}>
                  {steps.map(step => (
                    <div key={step.id} style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                            Step {step.step_number}: {step.tone_display}
                          </div>
                          <div style={{ fontSize: '13px', color: '#6b7280' }}>
                            Trigger: {step.offset_from_due !== null
                              ? `${step.offset_from_due} days ${step.offset_from_due < 0 ? 'before' : 'after'} due date`
                              : `${step.offset_from_issue} days from invoice issue`}
                          </div>
                          <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                            Approval: {step.approval_mode_display}
                            {step.is_final_notice && <span style={{ marginLeft: '8px', color: '#dc2626', fontWeight: 500 }}>(Final Notice)</span>}
                          </div>
                        </div>
                        <div style={{
                          padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
                          background: step.enabled ? '#d1fae5' : '#fee2e2',
                          color: step.enabled ? '#065f46' : '#991b1b'
                        }}>
                          {step.enabled ? 'Enabled' : 'Disabled'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}"""

if OLD4 in content:
    content = content.replace(OLD4, NEW4, 1)
    print("Change 4 OK")
else:
    print("FAIL: Change 4 marker not found")
    # Try to find partial match for debugging
    idx = content.find("view === 'schedules' && (")
    if idx >= 0:
        print(f"  Found schedules view at index {idx}")
        snippet = content[idx:idx+300]
        print(f"  Snippet: {repr(snippet)}")
    sys.exit(1)

# ── Change 5: insert archive confirmation modal after showScheduleModal block ──

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

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)

new_len = len(content)
print(f"Done. File size: {original_len} -> {new_len} bytes (+{new_len - original_len})")
