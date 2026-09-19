/**
 * Translation dictionaries for the Retinex frontend.
 *
 * IMPORTANT — MEDICAL TRANSLATION DISCLAIMER: these translations, especially
 * the referral recommendations and quality-gate guidance, have NOT been
 * reviewed by a native-speaking clinician. A mistranslation of something
 * like "urgent referral within days" vs "routine rescreen in 12 months" is
 * not a cosmetic bug in a healthcare tool — it could cause real harm.
 * Treat every non-English translation here as a draft. Before real
 * deployment in any language, have a native speaker with clinical
 * familiarity review every string in the RECOMMENDATIONS and quality
 * "reasons"/"guidance" sections at minimum.
 *
 * To add a new language: copy the `en` object below, translate every
 * value (never change the keys), and add it under its language code here.
 * Then add one line to LANGUAGES in I18nContext.jsx. Nothing else needs
 * to change — every component reads strings through the t() function.
 */

export const LANGUAGES = {
  en: { label: 'English', native: 'English' },
  hi: { label: 'Hindi', native: 'हिन्दी' },
};

const en = {
  // Top bar
  brand: 'Retinex',
  brandSubtitle: 'DR screening prototype',
  navScreen: 'Screen',
  navWorklist: 'Worklist',
  navPlanning: 'District Planning',
  engineTensorflow: 'engine: tensorflow',
  engineMock: 'engine: mock',
  engineUnreachable: 'backend unreachable',
  demoModeChip: 'Demo mode — no trained model loaded',

  // Screen page
  screenTitle: 'Screen a fundus image',
  screenSubtitle: "Upload or capture a retinal photograph. Images that aren't gradable are flagged for recapture before anything is graded.",
  dropzoneText: 'Drop a fundus image here, or click to browse',
  dropzoneHint: 'JPG or PNG · works from a phone camera in the field',
  loadingText: 'Assessing quality, enhancing, grading…',

  // Rejected
  rejectedTitle: '⚠ Image rejected',
  qualityScoreLabel: 'Quality score',
  tryAnotherImage: 'Try another image',

  // Quality reasons (returned by backend as codes; translated here)
  reason_out_of_focus: 'out of focus',
  reason_poor_illumination: 'poor illumination',
  reason_insufficient_field_of_view: 'insufficient field of view',
  reason_unreadable_file: 'unreadable file',
  guidancePrefix: 'Please recapture:',

  // Grade / evidence
  referableYes: '🔴 Referable DR',
  referableNo: '🟢 Not referable',
  confidenceLabel: 'Confidence',
  levelLabel: 'Level',

  level_0: 'No DR',
  level_1: 'Mild',
  level_2: 'Moderate',
  level_3: 'Severe',
  level_4: 'PDR',

  // Recommendations (returned by backend as codes; translated here)
  rec_routine_12mo: 'Routine rescreen in 12 months',
  rec_routine_6to12mo: 'Rescreen in 6-12 months',
  rec_refer_1mo: 'Refer to ophthalmologist within 1 month',
  rec_refer_2wk: 'Refer to ophthalmologist within 2 weeks',
  rec_urgent: 'Urgent referral (within days)',

  microaneurysms: 'microaneurysms',
  hemorrhages: 'hemorrhages',
  exudateArea: 'exudate area',
  lesionsInAttention: '% lesions inside attention region',
  consistentOk: '✓ AI grade is consistent with visible lesion evidence.',
  consistentWarn: '⚠ Evidence and AI grade disagree — review carefully.',

  metaQuality: 'Quality',
  metaProcessedIn: 'Processed in',
  metaEngine: 'Engine',

  // Review actions
  accept: '✓ Accept (A)',
  overrideTitle: 'Override to level',
  keyhint: 'A accept · 0–4 override level · N next image',
  reviewedNote: 'Review recorded ✓',
  reviewingTimer: 'reviewing',

  sessionLabel: 'Session',
  sessionReviewed: 'reviewed',
  sessionAvg: 'avg',
  sessionUnder30: 'under 30s',
  sessionOverridden: 'overridden',

  openReport: 'Open report ↗',
  screenAnother: 'Screen another image (N)',

  // Worklist page
  worklistTitle: 'Worklist',
  worklistSubtitle: 'Referable and inconsistent cases are surfaced first. Reload after screening new images.',
  refresh: 'Refresh',
  worklistLoading: 'Loading…',
  worklistEmpty: 'No cases yet — screen an image to get started.',
  colId: 'ID',
  colGrade: 'Grade',
  colReferable: 'Referable',
  colConsistent: 'Consistent',
  colStatus: 'Status',
  colTime: 'Time',
  statusRejected: 'rejected',
  statusReviewed: 'reviewed',
  statusPending: 'pending review',
  statusQualityReject: 'quality reject',
  reportLink: 'report',
  yes: 'yes',
  no: 'no',

  // Planning page
  planningTitle: 'District screening capacity planning',
  planningSubtitle: 'Adjust the sliders to size a screening program — find the smallest reviewer/bandwidth setup that keeps the backlog under control.',
  ctrl_num_sites: 'Camera sites',
  ctrl_patients_per_site_per_day: 'Patients / site / day',
  ctrl_upload_bandwidth_mbps: 'Upload bandwidth (Mbps)',
  ctrl_ai_seconds_per_image: 'AI seconds / image',
  ctrl_review_fraction: 'Fraction needing review',
  ctrl_review_seconds: 'Review seconds / image',
  ctrl_num_reviewers: 'Ophthalmologists / reviewers',

  statPatientsPerYear: 'Patients / year at these settings',
  statBacklogClear: 'Time to clear peak review backlog',
  statUtilization: 'Reviewer utilization',
  statBottleneck: 'Current bottleneck',
  bottleneck_upload_bandwidth: 'upload bandwidth',
  bottleneck_ai_processing: 'ai processing',
  bottleneck_human_review: 'human review',

  capacityNote: 'Capacity per hour — upload:',
  capacityAi: 'AI:',
  capacityReview: 'review:',
  capacityIncoming: 'incoming:',
  capacityImagesPerHr: 'images/hr',

  chartTitle: 'Queue length over the simulated period',
  legendUpload: 'Upload queue',
  legendAi: 'AI processing queue',
  legendReview: 'Human review queue',
};

const hi = {
  brand: 'Retinex',
  brandSubtitle: 'डीआर जांच प्रोटोटाइप',
  navScreen: 'जांच',
  navWorklist: 'कार्य सूची',
  navPlanning: 'जिला योजना',
  engineTensorflow: 'इंजन: टेंसरफ़्लो',
  engineMock: 'इंजन: डेमो',
  engineUnreachable: 'बैकएंड से संपर्क नहीं',
  demoModeChip: 'डेमो मोड — कोई प्रशिक्षित मॉडल लोड नहीं',

  screenTitle: 'फंडस छवि की जांच करें',
  screenSubtitle: 'रेटिना की तस्वीर अपलोड करें या लें। जो छवियां जांचने योग्य नहीं हैं उन्हें ग्रेड करने से पहले दोबारा फ़ोटो लेने के लिए चिह्नित किया जाएगा।',
  dropzoneText: 'यहां फंडस छवि छोड़ें, या ब्राउज़ करने के लिए क्लिक करें',
  dropzoneHint: 'JPG या PNG · फोन कैमरे से भी काम करता है',
  loadingText: 'गुणवत्ता जांच, सुधार और श्रेणीकरण हो रहा है…',

  rejectedTitle: '⚠ छवि अस्वीकृत',
  qualityScoreLabel: 'गुणवत्ता स्कोर',
  tryAnotherImage: 'दूसरी छवि आज़माएं',

  reason_out_of_focus: 'फोकस से बाहर',
  reason_poor_illumination: 'खराब रोशनी',
  reason_insufficient_field_of_view: 'अपर्याप्त फ्रेम कवरेज',
  reason_unreadable_file: 'फ़ाइल पढ़ने योग्य नहीं',
  guidancePrefix: 'कृपया दोबारा फ़ोटो लें:',

  referableYes: '🔴 विशेषज्ञ रेफरल आवश्यक',
  referableNo: '🟢 रेफरल आवश्यक नहीं',
  confidenceLabel: 'विश्वास स्तर',
  levelLabel: 'स्तर',

  level_0: 'डीआर नहीं',
  level_1: 'हल्का',
  level_2: 'मध्यम',
  level_3: 'गंभीर',
  level_4: 'पीडीआर',

  rec_routine_12mo: '12 महीने में नियमित जांच',
  rec_routine_6to12mo: '6-12 महीने में दोबारा जांच',
  rec_refer_1mo: '1 महीने के भीतर नेत्र विशेषज्ञ को दिखाएं',
  rec_refer_2wk: '2 सप्ताह के भीतर नेत्र विशेषज्ञ को दिखाएं',
  rec_urgent: 'तत्काल रेफरल आवश्यक (कुछ दिनों में)',

  microaneurysms: 'माइक्रोएन्यूरिज्म',
  hemorrhages: 'रक्तस्राव',
  exudateArea: 'एक्सयूडेट क्षेत्र',
  lesionsInAttention: '% घाव मॉडल के ध्यान क्षेत्र में',
  consistentOk: '✓ एआई ग्रेड दृश्य साक्ष्य से मेल खाता है।',
  consistentWarn: '⚠ साक्ष्य और एआई ग्रेड में असमानता — ध्यान से जांचें।',

  metaQuality: 'गुणवत्ता',
  metaProcessedIn: 'प्रोसेसिंग समय',
  metaEngine: 'इंजन',

  accept: '✓ स्वीकार करें (A)',
  overrideTitle: 'स्तर बदलें',
  keyhint: 'A स्वीकार करें · 0–4 स्तर बदलें · N अगली छवि',
  reviewedNote: 'समीक्षा दर्ज हुई ✓',
  reviewingTimer: 'समीक्षा हो रही है',

  sessionLabel: 'सत्र',
  sessionReviewed: 'समीक्षित',
  sessionAvg: 'औसत',
  sessionUnder30: '30 सेकंड से कम',
  sessionOverridden: 'बदला गया',

  openReport: 'रिपोर्ट खोलें ↗',
  screenAnother: 'अगली छवि जांचें (N)',

  worklistTitle: 'कार्य सूची',
  worklistSubtitle: 'रेफरल योग्य और असंगत मामले सबसे पहले दिखाए जाते हैं। नई छवियां जांचने के बाद पेज रीलोड करें।',
  refresh: 'रीफ्रेश करें',
  worklistLoading: 'लोड हो रहा है…',
  worklistEmpty: 'अभी तक कोई मामला नहीं — शुरू करने के लिए एक छवि जांचें।',
  colId: 'आईडी',
  colGrade: 'ग्रेड',
  colReferable: 'रेफरल',
  colConsistent: 'सुसंगत',
  colStatus: 'स्थिति',
  colTime: 'समय',
  statusRejected: 'अस्वीकृत',
  statusReviewed: 'समीक्षित',
  statusPending: 'समीक्षा लंबित',
  statusQualityReject: 'गुणवत्ता में अस्वीकृत',
  reportLink: 'रिपोर्ट',
  yes: 'हां',
  no: 'नहीं',

  planningTitle: 'जिला जांच क्षमता योजना',
  planningSubtitle: 'बैकलॉग को नियंत्रण में रखने वाली सबसे छोटी समीक्षक/बैंडविड्थ व्यवस्था खोजने के लिए स्लाइडर समायोजित करें।',
  ctrl_num_sites: 'कैमरा केंद्र',
  ctrl_patients_per_site_per_day: 'मरीज़ / केंद्र / दिन',
  ctrl_upload_bandwidth_mbps: 'अपलोड बैंडविड्थ (Mbps)',
  ctrl_ai_seconds_per_image: 'एआई सेकंड / छवि',
  ctrl_review_fraction: 'समीक्षा की आवश्यकता वाला अंश',
  ctrl_review_seconds: 'समीक्षा सेकंड / छवि',
  ctrl_num_reviewers: 'नेत्र विशेषज्ञ / समीक्षक',

  statPatientsPerYear: 'इन सेटिंग्स पर प्रति वर्ष मरीज़',
  statBacklogClear: 'अधिकतम बैकलॉग साफ़ करने का समय',
  statUtilization: 'समीक्षक उपयोग',
  statBottleneck: 'वर्तमान बाधा',
  bottleneck_upload_bandwidth: 'अपलोड बैंडविड्थ',
  bottleneck_ai_processing: 'एआई प्रोसेसिंग',
  bottleneck_human_review: 'मानव समीक्षा',

  capacityNote: 'क्षमता प्रति घंटा — अपलोड:',
  capacityAi: 'एआई:',
  capacityReview: 'समीक्षा:',
  capacityIncoming: 'आगमन:',
  capacityImagesPerHr: 'छवियां/घंटा',

  chartTitle: 'सिम्युलेशन अवधि में कतार की लंबाई',
  legendUpload: 'अपलोड कतार',
  legendAi: 'एआई प्रोसेसिंग कतार',
  legendReview: 'मानव समीक्षा कतार',
};

export const TRANSLATIONS = { en, hi };
