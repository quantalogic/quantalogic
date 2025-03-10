import React, { useEffect, useState } from 'react';

interface ValidationDialogProps {
  validationId: string;
  question: string;
  onValidate: (approved: boolean) => void;
}

export const ValidationDialog: React.FC<ValidationDialogProps> = ({
  validationId,
  question,
  onValidate,
}) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full">
        <h2 className="text-lg font-semibold mb-4">Validation Required</h2>
        <p className="mb-6 whitespace-pre-wrap">{question}</p>
        <div className="flex justify-end space-x-4">
          <button
            onClick={() => onValidate(false)}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
          >
            Deny
          </button>
          <button
            onClick={() => onValidate(true)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
};
