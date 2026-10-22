import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { supportApi } from '../api/client';
import SupportModal from '../components/common/SupportModal';

vi.mock('../api/client', () => ({
  supportApi: { send: vi.fn() },
}));

const mockedSend = vi.mocked(supportApi.send);

describe('SupportModal', () => {
  beforeEach(() => {
    mockedSend.mockReset();
    mockedSend.mockResolvedValue({ data: { delivered: 1 } } as never);
  });

  it('sends a support message with the current section and closes', async () => {
    const onClose = vi.fn();
    render(<SupportModal open onClose={onClose} />);

    const send = screen.getByRole('button', { name: 'Отправить' });
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Сообщение'), {
      target: { value: 'Не получается изменить расписание на 15 минут' },
    });
    expect(send).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(send);
    });

    await waitFor(() =>
      expect(mockedSend).toHaveBeenCalledWith({
        message: 'Не получается изменить расписание на 15 минут',
        page: window.location.pathname,
      }),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the backend error and keeps the form open', async () => {
    mockedSend.mockRejectedValueOnce({
      response: { data: { detail: 'Поддержка временно недоступна' }, status: 503 },
    });
    const onClose = vi.fn();
    render(<SupportModal open onClose={onClose} />);

    fireEvent.change(screen.getByLabelText('Сообщение'), {
      target: { value: 'Помогите с расписанием, пожалуйста' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Отправить' }));
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Поддержка временно недоступна',
    );
    expect(onClose).not.toHaveBeenCalled();
  });
});
