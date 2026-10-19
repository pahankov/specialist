import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ContactsCard, { type ContactsApi } from '../components/profile/ContactsCard';
import type { ClientContact } from '../api/cabinet';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const PHONE: ClientContact = {
  id: 1,
  contact_type: 'phone',
  value: '+7 (961) 520-23-11',
  is_primary: true,
  is_verified: true,
  verified_via: 'social',
};

const EMAIL: ClientContact = {
  id: 2,
  contact_type: 'email',
  value: 'info@example.com',
  is_primary: true,
  is_verified: false,
  verified_via: null,
};

function makeApi(): ContactsApi {
  return {
    addContact: vi.fn().mockResolvedValue({}),
    removeContact: vi.fn().mockResolvedValue({}),
    makeContactPrimary: vi.fn().mockResolvedValue({}),
    sendContactCode: vi.fn().mockResolvedValue({}),
    verifyContactCode: vi.fn().mockResolvedValue({}),
  };
}

describe('ContactsCard (injected API — super profile reuse)', () => {
  it('adds a phone through the injected API and refreshes', async () => {
    const api = makeApi();
    const onChanged = vi.fn();
    render(<ContactsCard contacts={[PHONE, EMAIL]} onChanged={onChanged} api={api} />);

    fireEvent.change(screen.getByPlaceholderText('+7 (999) 123-45-67'), {
      target: { value: '+79990001122' },
    });
    const btn = screen.getByRole('button', { name: 'Добавить' });
    // jsdom doesn't submit forms on button click — submit the form directly.
    fireEvent.submit(btn.closest('form') as HTMLFormElement);

    await waitFor(() =>
      expect(api.addContact).toHaveBeenCalledWith({
        contact_type: 'phone',
        value: '+7 (999) 000-11-22',
      }),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it('promotes and removes through the injected API', async () => {
    const api = makeApi();
    const onChanged = vi.fn();
    render(
      <ContactsCard
        contacts={[{ ...PHONE, is_primary: false }, EMAIL]}
        onChanged={onChanged}
        api={api}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Сделать основным' }));
    await waitFor(() => expect(api.makeContactPrimary).toHaveBeenCalledWith(PHONE.id));

    fireEvent.click(screen.getAllByTitle('Удалить контакт')[0]);
    await waitFor(() => expect(api.removeContact).toHaveBeenCalledWith(PHONE.id));
    expect(onChanged).toHaveBeenCalledTimes(2);
  });
});
