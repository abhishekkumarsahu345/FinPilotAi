/**
 * Complete Reminders Page Component for FinPilot AI
 * 
 * INTEGRATION INSTRUCTIONS:
 * 
 * 1. In App.tsx, find the line:
 *    {page === 'Reminders' && <div>Coming soon...</div>}
 * 
 * 2. Replace it with:
 *    {page === 'Reminders' && selectedOrg && (
 *      <RemindersPage org={selectedOrg} />
 *    )}
 * 
 * 3. Copy the RemindersPage component function below into App.tsx
 *    (place it after the SettingsScreen component and before the main App function)
 * 
 * 4. Update the sidebar navigation:
 *    Find: { name: 'Reminders', icon: Bell, soon: true }
 *    Change to: { name: 'Reminders', icon: Bell }
 */

function RemindersPage({ org }: { org: Org }) {
  const [view, setView] = useState<'pending' | 'sent' | 'failed' | 'schedules'>('pending')
  const [schedules, setSchedules] = useState<ReminderSchedule[]>([])
  const [steps, setSteps] = useState<ReminderStep[]>([])
  const [jobs, setJobs] = useState<ReminderJob[]>([])
  const [selectedSchedule, setSelectedSchedule] = useState<ReminderSchedule | null>(null)
  const [previewJob, setPreviewJob] = useState<ReminderJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Modal states
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [showStepModal, setShowStepModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ReminderSchedule | null>(null)
  const [editingStep, setEditingStep] = useState<ReminderStep | null>(null)

  // Approval form state
  const [customIntro, setCustomIntro] = useState('')
  const [customClosing, setCustomClosing] = useState('')

  // Load data
  const loadSchedules = useCallback(async () => {
    try {
      const data = await api.reminderSchedules(org.id)
      setSchedules(data.results)
    } catch (err) {
      console.error('Failed to load schedules:', err)
    }
  }, [org.id])

  const loadSteps = useCallback(async (scheduleId?: string) => {
    try {
      const data = await api.reminderSteps(org.id, scheduleId)
      setSteps(data.results)
    } catch (err) {
      console.error('Failed to load steps:', err)
    }
  }, [org.id])

  const loadJobs = useCallback(async (status?: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.reminderJobs(org.id, { status, include_preview: false })
      setJobs(data.results)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load reminders')
    } finally {
      setLoading(false)
    }
  }, [org.id])

  // Initial load
  useEffect(() => {
    loadSchedules()
    if (view === 'pending') loadJobs('proposed')
    else if (view === 'sent') loadJobs('dispatched')
    else if (view === 'failed') loadJobs('failed')
  }, [view, loadSchedules, loadJobs])

  // Seed default setup
  const handleSeedDefaults = async () => {
    if (!confirm('Create default 4-step reminder schedule? This will create:\n- Invoice Issue Notification\n- 7 days before due reminder\n- 3 days after due reminder\n- 15 days after due final notice')) return
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const result = await api.seedDefaultReminders(org.id)
      setSuccess(`${result.message} (${result.steps_created} steps created)`)
      await loadSchedules()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to seed defaults')
    } finally {
      setLoading(false)
    }
  }

  // Preview reminder
  const handlePreview = async (job: ReminderJob) => {
    setLoading(true)
    try {
      const fullJob = await api.getReminderJobWithPreview(org.id, job.id)
      setPreviewJob(fullJob)
      setCustomIntro(fullJob.approved_custom_intro || '')
      setCustomClosing(fullJob.approved_custom_closing || '')
      setShowPreviewModal(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load preview')
    } finally {
      setLoading(false)
    }
  }

  // Approve reminder
  const handleApprove = async () => {
    if (!previewJob) return
    setLoading(true)
    setError('')
    try {
      await api.approveReminderJob(org.id, previewJob.id, {
        custom_intro: customIntro,
        custom_closing: customClosing,
      })
      setSuccess('Reminder approved and queued for sending')
      setShowPreviewModal(false)
      setPreviewJob(null)
      await loadJobs(view === 'pending' ? 'proposed' : view === 'sent' ? 'dispatched' : 'failed')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to approve reminder')
    } finally {
      setLoading(false)
    }
  }

  // Reject reminder
  const handleReject = async (jobId: string) => {
    if (!confirm('Reject this reminder? It will not be sent.')) return
    setLoading(true)
    setError('')
    try {
      await api.rejectReminderJob(org.id, jobId)
      setSuccess('Reminder rejected')
      await loadJobs('proposed')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to reject reminder')
    } finally {
      setLoading(false)
    }
  }

  // Count by status
  const pendingCount = jobs.filter(j => j.status === 'proposed').length
  const sentTodayCount = jobs.filter(j => j.status === 'dispatched' && j.dispatched_at?.startsWith(new Date().toISOString().split('T')[0])).length
  const failedCount = jobs.filter(j => j.status === 'failed').length

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: '28px', fontWeight: 600 }}>Payment Reminders</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          {schedules.length === 0 && (
            <button onClick={handleSeedDefaults} disabled={loading} style={{
              padding: '10px 20px', background: '#3b82f6', color: 'white', border: 'none',
              borderRadius: '6px', cursor: 'pointer', fontWeight: 500
            }}>
              Set Up Reminders
            </button>
          )}
          <button onClick={() => { setEditingSchedule(null); setShowScheduleModal(true) }} style={{
            padding: '10px 20px', background: '#10b981', color: 'white', border: 'none',
            borderRadius: '6px', cursor: 'pointer', fontWeight: 500
          }}>
            <Plus size={16} style={{ verticalAlign: 'middle', marginRight: '6px' }} />
            New Schedule
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div style={{ padding: '12px', background: '#fee', border: '1px solid #fcc', borderRadius: '6px', marginBottom: '16px', color: '#c00' }}>
          {error}
          <button onClick={() => setError('')} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>
      )}
      {success && (
        <div style={{ padding: '12px', background: '#efe', border: '1px solid #cfc', borderRadius: '6px', marginBottom: '16px', color: '#060' }}>
          {success}
          <button onClick={() => setSuccess('')} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>
      )}

      {/* View Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '2px solid #e5e7eb' }}>
        <button onClick={() => setView('pending')} style={{
          padding: '12px 24px', background: view === 'pending' ? '#fff' : 'transparent',
          border: 'none', borderBottom: view === 'pending' ? '3px solid #3b82f6' : '3px solid transparent',
          cursor: 'pointer', fontWeight: 500, color: view === 'pending' ? '#3b82f6' : '#6b7280'
        }}>
          Pending Approvals {pendingCount > 0 && <span style={{ marginLeft: '6px', padding: '2px 8px', background: '#fee', borderRadius: '12px', fontSize: '12px', color: '#c00' }}>{pendingCount}</span>}
        </button>
        <button onClick={() => setView('sent')} style={{
          padding: '12px 24px', background: view === 'sent' ? '#fff' : 'transparent',
          border: 'none', borderBottom: view === 'sent' ? '3px solid #3b82f6' : '3px solid transparent',
          cursor: 'pointer', fontWeight: 500, color: view === 'sent' ? '#3b82f6' : '#6b7280'
        }}>
          Sent History
        </button>
        <button onClick={() => setView('failed')} style={{
          padding: '12px 24px', background: view === 'failed' ? '#fff' : 'transparent',
          border: 'none', borderBottom: view === 'failed' ? '3px solid #3b82f6' : '3px solid transparent',
          cursor: 'pointer', fontWeight: 500, color: view === 'failed' ? '#3b82f6' : '#6b7280'
        }}>
          Failed {failedCount > 0 && <span style={{ marginLeft: '6px', padding: '2px 8px', background: '#fee', borderRadius: '12px', fontSize: '12px', color: '#c00' }}>{failedCount}</span>}
        </button>
        <button onClick={() => setView('schedules')} style={{
          padding: '12px 24px', background: view === 'schedules' ? '#fff' : 'transparent',
          border: 'none', borderBottom: view === 'schedules' ? '3px solid #3b82f6' : '3px solid transparent',
          cursor: 'pointer', fontWeight: 500, color: view === 'schedules' ? '#3b82f6' : '#6b7280'
        }}>
          Schedules ({schedules.length})
        </button>
      </div>

      {/* Content */}
      {loading && <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Loading...</div>}

      {!loading && view === 'pending' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Awaiting Your Approval</h2>
          {jobs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
              <Bell size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <div>No pending reminders to approve</div>
            </div>
          ) : (
            <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Invoice</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Customer</th>
                    <th style={{ padding: '12px', textAlign: 'right', fontWeight: 600 }}>Outstanding</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Due Date</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Step</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Scheduled</th>
                    <th style={{ padding: '12px', textAlign: 'right', fontWeight: 600 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: '12px' }}>{job.invoice_number}</td>
                      <td style={{ padding: '12px' }}>{job.customer_name}</td>
                      <td style={{ padding: '12px', textAlign: 'right', fontWeight: 600, color: job.snapshot_days_overdue > 0 ? '#dc2626' : '#059669' }}>
                        {money(job.current_outstanding_minor || job.snapshot_outstanding_minor)}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {fmtDate(job.snapshot_due_date)}
                        {job.snapshot_days_overdue > 0 && (
                          <span style={{ marginLeft: '8px', fontSize: '12px', color: '#dc2626' }}>
                            ({job.snapshot_days_overdue} days overdue)
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '12px' }}>
                        <span style={{
                          padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
                          background: job.step_tone === 'issue' ? '#dbeafe' : job.step_tone === 'friendly' ? '#d1fae5' : job.step_tone === 'gentle' ? '#fef3c7' : '#fee2e2',
                          color: job.step_tone === 'issue' ? '#1e40af' : job.step_tone === 'friendly' ? '#065f46' : job.step_tone === 'gentle' ? '#92400e' : '#991b1b'
                        }}>
                          Step {job.step_number}
                        </span>
                      </td>
                      <td style={{ padding: '12px' }}>{fmtDate(job.scheduled_date)}</td>
                      <td style={{ padding: '12px', textAlign: 'right' }}>
                        <button onClick={() => handlePreview(job)} style={{ padding: '6px 12px', background: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '8px', fontSize: '13px' }}>
                          Preview & Approve
                        </button>
                        <button onClick={() => handleReject(job.id)} style={{ padding: '6px 12px', background: '#ef4444', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}>
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && view === 'sent' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Sent Reminders</h2>
          {jobs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>No sent reminders yet</div>
          ) : (
            <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Sent At</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Invoice</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Customer</th>
                    <th style={{ padding: '12px', textAlign: 'right', fontWeight: 600 }}>Amount Sent For</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Step</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: '12px' }}>{job.dispatched_at ? new Date(job.dispatched_at).toLocaleString('en-IN') : '—'}</td>
                      <td style={{ padding: '12px' }}>{job.invoice_number}</td>
                      <td style={{ padding: '12px' }}>{job.customer_name}</td>
                      <td style={{ padding: '12px', textAlign: 'right' }}>{money(job.sent_outstanding_minor || job.snapshot_outstanding_minor)}</td>
                      <td style={{ padding: '12px' }}>Step {job.step_number}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && view === 'failed' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px', color: '#dc2626' }}>Failed Deliveries</h2>
          {jobs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
              <CheckCircle size={48} style={{ color: '#10b981', marginBottom: '16px' }} />
              <div>No failed deliveries</div>
            </div>
          ) : (
            <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Invoice</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Customer</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Error</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 600 }}>Retry Count</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: '12px' }}>{job.invoice_number}</td>
                      <td style={{ padding: '12px' }}>{job.customer_name}</td>
                      <td style={{ padding: '12px', color: '#dc2626', fontSize: '13px' }}>{job.block_reason || 'Unknown error'}</td>
                      <td style={{ padding: '12px' }}>{job.retry_count || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

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
                        {schedule.step_count} steps • Business hours: {schedule.send_hour_start}:00 - {schedule.send_hour_end}:00
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
                  <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{
                    padding: '8px 16px', background: '#f3f4f6', border: 'none',
                    borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'
                  }}>
                    View Steps →
                  </button>
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
      )}

      {/* Email Preview Modal */}
      {showPreviewModal && previewJob && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center',
          alignItems: 'center', zIndex: 1000, padding: '20px'
        }}>
          <div style={{
            background: 'white', borderRadius: '8px', maxWidth: '900px',
            width: '100%', maxHeight: '90vh', overflow: 'hidden', display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Modal Header */}
            <div style={{ padding: '20px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
                Preview & Approve Reminder: {previewJob.invoice_number}
              </h2>
              <button onClick={() => { setShowPreviewModal(false); setPreviewJob(null) }} style={{
                background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280'
              }}>
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
              {/* Invoice Info */}
              <div style={{ background: '#f9fafb', padding: '16px', borderRadius: '6px', marginBottom: '20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', fontSize: '14px' }}>
                  <div>
                    <div style={{ color: '#6b7280', marginBottom: '4px' }}>Customer</div>
                    <div style={{ fontWeight: 600 }}>{previewJob.customer_name}</div>
                    <div style={{ fontSize: '13px', color: '#6b7280' }}>{previewJob.customer_email}</div>
                  </div>
                  <div>
                    <div style={{ color: '#6b7280', marginBottom: '4px' }}>Outstanding</div>
                    <div style={{ fontWeight: 600, fontSize: '18px', color: previewJob.snapshot_days_overdue > 0 ? '#dc2626' : '#059669' }}>
                      {money(previewJob.current_outstanding_minor || previewJob.snapshot_outstanding_minor)}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#6b7280', marginBottom: '4px' }}>Due Date</div>
                    <div style={{ fontWeight: 600 }}>{fmtDate(previewJob.snapshot_due_date)}</div>
                    {previewJob.snapshot_days_overdue > 0 && (
                      <div style={{ fontSize: '13px', color: '#dc2626' }}>{previewJob.snapshot_days_overdue} days overdue</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Custom Messages */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  Custom Introduction (optional)
                </label>
                <textarea
                  value={customIntro}
                  onChange={e => setCustomIntro(e.target.value)}
                  placeholder="Add a personal message at the beginning of the email..."
                  style={{
                    width: '100%', padding: '10px', border: '1px solid #e5e7eb',
                    borderRadius: '6px', fontSize: '14px', resize: 'vertical', minHeight: '60px'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  Custom Closing (optional)
                </label>
                <textarea
                  value={customClosing}
                  onChange={e => setCustomClosing(e.target.value)}
                  placeholder="Add a personal message at the end of the email..."
                  style={{
                    width: '100%', padding: '10px', border: '1px solid #e5e7eb',
                    borderRadius: '6px', fontSize: '14px', resize: 'vertical', minHeight: '60px'
                  }}
                />
              </div>

              {/* Email Preview */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ fontWeight: 500, marginBottom: '8px' }}>Email Subject:</div>
                <div style={{ padding: '10px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '14px' }}>
                  {previewJob.email_preview_subject || `Payment Reminder: Invoice ${previewJob.invoice_number}`}
                </div>
              </div>

              <div>
                <div style={{ fontWeight: 500, marginBottom: '8px' }}>Email Body Preview:</div>
                <div style={{
                  border: '1px solid #e5e7eb', borderRadius: '6px', padding: '20px',
                  background: '#f9fafb', maxHeight: '400px', overflowY: 'auto'
                }}>
                  {previewJob.email_preview_html ? (
                    <iframe
                      srcDoc={previewJob.email_preview_html}
                      style={{ width: '100%', height: '400px', border: 'none', background: 'white' }}
                      title="Email Preview"
                    />
                  ) : (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
                      Email preview not available
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{ padding: '20px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button onClick={() => { setShowPreviewModal(false); setPreviewJob(null) }} style={{
                padding: '10px 20px', background: '#f3f4f6', border: 'none',
                borderRadius: '6px', cursor: 'pointer', fontWeight: 500
              }}>
                Cancel
              </button>
              <button onClick={handleApprove} disabled={loading} style={{
                padding: '10px 20px', background: '#10b981', color: 'white', border: 'none',
                borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 500,
                opacity: loading ? 0.5 : 1
              }}>
                {loading ? 'Approving...' : 'Approve & Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
