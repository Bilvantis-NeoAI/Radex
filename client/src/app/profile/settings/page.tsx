'use client';

import SettingsPanel from '@/components/settings/SettingsPanel';

export default function ProfileSettingsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Profile Settings</h1>
      <SettingsPanel />
    </div>
  );
}
