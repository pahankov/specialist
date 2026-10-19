import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import EmailVerifyModal from '../components/profile/EmailVerifyModal';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

describe('EmailVerifyModal («Подтвердить почту»)', () => {
  it('auto-sends a code on open and verifies the entered digits', async () => {
    const sendCode = vi.fn().mockResolvedValue({});
    const verifyCode = vi.fn().mockResolvedValue({});
    const onVerified = vi.fn();
    const onClose = vi.fn();

    render(
      <EmailVerifyModal
        open
        email="user@example.com"
        onClose={onClose}
        sendCode={sendCode}
        verifyCode={verifyCode}
        onVerified={onVerified}
      />,
    );

    await waitFor(() => expect(sendCode).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/Мы отправили код на user@example.com/)).toBeInTheDocument();

    const btn = screen.getByRole('button', { name: 'Подтвердить' });
    const input = screen.getByLabelText('Код из письма');
    fireEvent.change(input, { target: { value: '12' } });
    expect(btn).toBeDisabled();

    fireEvent.change(input, { target: { value: '123456' } });
    // jsdom doesn't submit forms on button click — submit the form directly.
    fireEvent.submit(btn.closest('form') as HTMLFormElement);
    await waitFor(() => expect(verifyCode).toHaveBeenCalledWith('123456'));
    expect(onVerified).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('locks the resend for a minute, then resends on demand', async () => {
    vi.useFakeTimers();
    try {
      const sendCode = vi.fn().mockResolvedValue({});

      render(
        <EmailVerifyModal
          open
          email="user@example.com"
          onClose={vi.fn()}
          sendCode={sendCode}
          verifyCode={vi.fn()}
          onVerified={vi.fn()}
        />,
      );

      await act(async () => {
        await Promise.resolve();
      });
      expect(sendCode).toHaveBeenCalledTimes(1);
      // Cool-down: right after the send the resend button is locked.
      expect(screen.getByRole('button', { name: /Отправить код ещё раз/ })).toBeDisabled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      const resend = screen.getByRole('button', { name: 'Отправить код ещё раз' });
      expect(resend).toBeEnabled();
      fireEvent.click(resend);
      await act(async () => {
        await Promise.resolve();
      });
      expect(sendCode).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
